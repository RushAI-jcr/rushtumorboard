/**
 * Central metadata for all tumor board agents.
 * Used by @mention dropdown, message list, workflow guide, and progress indicator.
 */

export interface AgentMeta {
    /** Internal agent name (matches agents.yaml) */
    id: string;
    /** Nurse-friendly display label */
    label: string;
    /** Short description for autocomplete and tooltips */
    description: string;
    /** Color for sender badge in chat */
    color: string;
    /** Emoji icon for quick visual scanning */
    icon: string;
    /** Workflow step number (0-based) shown during orchestration, null if not a step */
    step: number | null;
}

const AGENT_META: AgentMeta[] = [
    {
        id: 'Orchestrator',
        label: 'Orchestrator',
        description: 'Runs the full case review from start to finish',
        color: '#6B4C9A',
        icon: '🎯',
        step: null,
    },
    {
        id: 'PatientStatus',
        label: 'Pre-Meeting Check',
        description: 'Checks for missing data before starting',
        color: '#D13438',
        icon: '✅',
        step: 0,
    },
    {
        id: 'PatientHistory',
        label: 'Patient & Timeline',
        description: 'Demographics, medical history, clinical timeline',
        color: '#0078D4',
        icon: '📋',
        step: 1,
    },
    {
        id: 'OncologicHistory',
        label: 'Cancer History',
        description: 'Prior diagnoses, treatments, surgical history',
        color: '#008575',
        icon: '🏥',
        step: 2,
    },
    {
        id: 'Pathology',
        label: 'Pathology',
        description: 'Histology, IHC, molecular markers (BRCA, MMR, p53)',
        color: '#C239B3',
        icon: '🔬',
        step: 3,
    },
    {
        id: 'Radiology',
        label: 'Imaging',
        description: 'CT, MRI, PET, and ultrasound findings',
        color: '#E3008C',
        icon: '📊',
        step: 4,
    },
    {
        id: 'ClinicalGuidelines',
        label: 'NCCN Guidelines',
        description: 'Treatment recommendations based on NCCN guidelines',
        color: '#498205',
        icon: '📖',
        step: 6,
    },
    {
        id: 'ClinicalTrials',
        label: 'Clinical Trials',
        description: 'Open trials matching patient diagnosis and eligibility',
        color: '#DA3B01',
        icon: '🔍',
        step: 7,
    },
    {
        id: 'MedicalResearch',
        label: 'Literature Review',
        description: 'PubMed and journal article search',
        color: '#8764B8',
        icon: '📚',
        step: 8,
    },
    {
        id: 'ReportCreation',
        label: 'Report & Slides',
        description: 'Generates Word doc and PowerPoint for tumor board',
        color: '#107C10',
        icon: '📄',
        step: 9,
    },
];

/** Lookup agent metadata by internal name (case-insensitive). */
export function getAgentMeta(agentId: string): AgentMeta | undefined {
    return AGENT_META.find(a => a.id.toLowerCase() === agentId.toLowerCase());
}

/** Get display label for an agent (falls back to the raw name). */
export function getAgentLabel(agentId: string): string {
    return getAgentMeta(agentId)?.label ?? agentId;
}

/** Get the color for an agent sender badge. */
export function getAgentColor(agentId: string): string {
    return getAgentMeta(agentId)?.color ?? '#616161';
}

/** Get all agent metadata entries. */
export function getAllAgentMeta(): AgentMeta[] {
    return AGENT_META;
}

/** Ordered workflow steps for the progress indicator. */
export const WORKFLOW_STEPS: AgentMeta[] = AGENT_META
    .filter(a => a.step !== null)
    .sort((a, b) => (a.step ?? 0) - (b.step ?? 0));

/**
 * Map ERROR_TYPE codes from backend to nurse-friendly messages.
 */
const ERROR_TRANSLATIONS: Record<string, string> = {
    'STORAGE_FAILED': 'The document could not be saved. Please try again or contact IT support.',
    'RENDER_DEGRADED': 'The report was created but some sections may be incomplete. Please review before printing.',
    'RENDER_FAILED': 'The report could not be created. Please try again or contact IT support.',
    'RENDER_TIMEOUT': 'The report is taking too long to generate. Please try again in a few minutes.',
};

/**
 * Translate backend error messages to nurse-friendly language.
 * Returns the original content if no ERROR_TYPE is found.
 */
export function translateErrorMessages(content: string): string {
    const errorMatch = content.match(/ERROR_TYPE:\s*(\w+)/);
    if (!errorMatch) return content;

    const errorType = errorMatch[1];
    const friendlyMessage = ERROR_TRANSLATIONS[errorType];
    if (!friendlyMessage) return content;

    // Keep any download URL that may be present
    const urlMatch = content.match(/Download URL:\s*(https?:\/\/\S+)/);
    const linkMatch = content.match(/<a href="[^"]+">([^<]+)<\/a>/);

    let result = friendlyMessage;
    if (urlMatch && linkMatch) {
        result += `\n\n[${linkMatch[1]}](${urlMatch[1]})`;
    }
    return result;
}
