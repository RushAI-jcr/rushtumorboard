# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import base64
import json
import logging
import uuid
from typing import Dict, List, Optional

from botframework.connector.auth import ClaimsIdentity
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class UserInfo(BaseModel):
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    roles: Optional[list] = None


def get_user_info_from_headers(request: Request) -> Dict:
    """
    Extract user info from the headers provided by Azure App Service authentication.

    When a user is authenticated via Azure App Service, it adds headers with user info.
    """
    logger.debug("Request: content-type=%s", request.headers.get("content-type", ""))

    # Headers from App Service Auth
    user_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "")
    user_name = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME", "")

    # Try to get full claims from the principal header
    principal_header = request.headers.get("X-MS-CLIENT-PRINCIPAL", "")

    email = ""
    roles: List[str] = []

    if principal_header:
        try:
            decoded = base64.b64decode(principal_header).decode('utf-8')
            user_details = json.loads(decoded)
            logger.debug("Decoded user principal: id_provider=%s", user_details.get("auth_typ", "unknown"))

            # Process claims using ClaimsIdentity if we have claims data
            if 'claims' in user_details and isinstance(user_details['claims'], list):
                # Convert from Azure App Service format to ClaimsIdentity format
                # App Service format: [{"typ": "claim_type", "val": "claim_value"}, ...]
                # Convert to: {"claim_type": ["claim_value"], ...}
                claim_dict = {}
                for claim in user_details['claims']:
                    claim_type = claim.get('typ')
                    claim_value = claim.get('val')
                    if claim_type and claim_value:
                        if claim_type not in claim_dict:
                            claim_dict[claim_type] = []
                        claim_dict[claim_type].append(claim_value)

                # Create a ClaimsIdentity object
                claims_identity = ClaimsIdentity(claims=claim_dict, is_authenticated=True)

                # Extract email from appropriate claims
                email_claims = [
                    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
                    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                    "preferred_username",
                    "email"
                ]

                for claim_type in email_claims:
                    claim_values = claims_identity.claims.get(claim_type)
                    if claim_values and len(claim_values) > 0:
                        email = claim_values[0]
                        if email:
                            break

                # If we still don't have an email, try the name claim if it looks like an email
                if not email:
                    name_claims = claims_identity.claims.get(
                        "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")
                    if name_claims and len(name_claims) > 0 and '@' in name_claims[0]:
                        email = name_claims[0]

                # Extract roles
                role_claims = claims_identity.claims.get(
                    "http://schemas.microsoft.com/ws/2008/06/identity/claims/role", [])
                roles = role_claims

        except Exception as e:
            logger.error(f"Error processing principal header: {e}")

    # If we couldn't find an email, try using the user_name as email (if it looks like an email)
    if not email and '@' in user_name:
        email = user_name

    return {
        "id": user_id,
        "name": user_name,
        "email": email,
        "roles": roles
    }


def user_routes():
    router = APIRouter()

    @router.get("/api/user/me", response_model=UserInfo)
    async def get_current_user(request: Request):
        """
        Endpoint to get information about the currently authenticated user.
        Uses App Service Authentication to get user info from headers.
        """
        try:
            user_info = get_user_info_from_headers(request)

            # If we don't have a user ID, authentication probably failed
            if not user_info["id"]:
                raise HTTPException(status_code=401, detail="User not authenticated")

            return JSONResponse(
                content=user_info
            )

        except Exception:
            ref = uuid.uuid4().hex[:8]
            logger.exception("Error getting user info [ref=%s]", ref)
            return JSONResponse(
                content={"error": f"An internal error occurred. Reference: {ref}"},
                status_code=500
            )

    return router
