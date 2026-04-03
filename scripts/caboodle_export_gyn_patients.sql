/*
 * Epic Clarity Export Queries — GYN Oncology Tumor Board
 * Rush University Medical Center
 *
 * PURPOSE:
 *   Export the 7 CSV files required by CaboodleFileAccessor for each patient.
 *   These queries target EPIC CLARITY (the transactional reporting database),
 *   NOT Caboodle/Cogito DWH — confirmed by PAT_ID UUID format and
 *   ORDER_ID|COMPONENT_ID composite ResultID in existing exports.
 *
 * HOW TO USE:
 *   1. Run the utility query at the bottom to find PAT_ID for your patients.
 *   2. For each patient, set @PAT_ID and run each block.
 *   3. Export results → Save as UTF-8 CSV with headers.
 *   4. Place in: infra/patient_data/{PAT_ID}/{file_type}.csv
 *      e.g., infra/patient_data/<YOUR-PAT-ID-HERE>/clinical_notes.csv
 *   5. Validate: python3 scripts/validate_patient_csvs.py
 *
 * SCHEMA:
 *   Tested against Epic Clarity schema (commonly 2022–2024 builds).
 *   Column aliases must match CaboodleFileAccessor exactly — do NOT rename them.
 *   PatientID column = Epic PAT_ID (GUID/UUID format).
 */

/* ============================================================
 * PARAMETERS — set per patient
 * ============================================================ */
DECLARE @PAT_ID  VARCHAR(50) = '<YOUR-PAT-ID-HERE>';
DECLARE @Days    INT         = 1825;   -- 5-year lookback

/* Helper: resolve to internal PAT_ENC_CSN_ID key set */
-- Most queries below join through PAT_ENC, which is keyed on PAT_ID.
-- Where a PATIENT.PAT_ID join is needed, it is done directly.


/* ============================================================
 * 1. CLINICAL NOTES
 * Output file: clinical_notes.csv
 * Columns: NoteID, PatientID, NoteType, EntryDate, NoteText
 * ============================================================ */
SELECT
    hn.NOTE_ID                                  AS NoteID,
    @PAT_ID                                     AS PatientID,
    COALESCE(znt.NAME, 'Note')                  AS NoteType,
    CONVERT(DATE, hn.NOTED_DATE)                AS EntryDate,
    -- Concatenate all note text segments in order
    (
        SELECT ISNULL(hnt.NOTE_TEXT, '') + ' '
        FROM HNO_NOTE_TEXT hnt
        WHERE hnt.NOTE_ID = hn.NOTE_ID
        ORDER BY hnt.LINE
        FOR XML PATH(''), TYPE
    ).value('(./text())[1]', 'NVARCHAR(MAX)')   AS NoteText
FROM HNO_NOTE_INFO hn
    JOIN PATIENT p
        ON p.PAT_ID = @PAT_ID
        AND hn.PAT_ID = p.PAT_ID
    LEFT JOIN ZC_NOTE_TYPE_IP znt
        ON znt.TYPE_IP_C = hn.IP_NOTE_TYPE_C
WHERE
    hn.NOTED_DATE >= DATEADD(DAY, -@Days, GETDATE())
    AND hn.SPEC_NOTE_TYPE_C IS NULL          -- exclude addenda-only records
    AND EXISTS (
        SELECT 1 FROM HNO_NOTE_TEXT hnt
        WHERE hnt.NOTE_ID = hn.NOTE_ID
        AND LEN(LTRIM(ISNULL(hnt.NOTE_TEXT, ''))) > 20
    )
    AND COALESCE(znt.NAME, '') IN (
        'History and Physical', 'H&P', 'Progress Notes', 'Progress Note',
        'Consult Note', 'Consultation', 'Operative Note', 'Procedure Note',
        'Discharge Summary', 'Oncology', 'Gynecology Oncology',
        'Office Visit', 'Result Encounter Note', 'Physician Notes'
    )
ORDER BY hn.NOTED_DATE DESC;

/*
 * ALTERNATIVE — if HNO_NOTE_INFO is not accessible in your Clarity schema,
 * use the Notes view from Reporting Workbench (MyChart/Caboodle side):
 *
 * SELECT
 *     n.NOTE_ID AS NoteID, @PAT_ID AS PatientID,
 *     n.NOTE_TYPE AS NoteType,
 *     CONVERT(DATE, n.NOTED_DATE) AS EntryDate,
 *     n.NOTE_TEXT AS NoteText
 * FROM V_NOTES_ALL n  -- or your custom note view
 * WHERE n.PAT_ID = @PAT_ID
 *   AND n.NOTED_DATE >= DATEADD(DAY, -@Days, GETDATE());
 */


/* ============================================================
 * 2. PATHOLOGY REPORTS
 * Output file: pathology_reports.csv
 * Columns: ReportID, PatientID, ProcedureName, OrderDate, ReportText
 *
 * NOTE: Many patients will legitimately have 0 rows here if surgery
 * was performed at an outside institution and only radiology follow-up
 * is at Rush. An empty file is valid — the accessor handles it.
 * ============================================================ */
SELECT
    op.ORDER_PROC_ID                            AS ReportID,
    @PAT_ID                                     AS PatientID,
    COALESCE(eap.PROC_NAME, 'Pathology')        AS ProcedureName,
    CONVERT(DATE, op.ORDER_TIME)                AS OrderDate,
    -- Pathology narrative: join result lines in order
    (
        SELECT ISNULL(orr.ORD_VALUE, '') + CHAR(10)
        FROM ORDER_RESULTS orr
        WHERE orr.ORDER_PROC_ID = op.ORDER_PROC_ID
          AND orr.LINE_COMMENT IS NULL
        ORDER BY orr.LINE
        FOR XML PATH(''), TYPE
    ).value('(./text())[1]', 'NVARCHAR(MAX)')   AS ReportText
FROM ORDER_PROC op
    JOIN PATIENT p
        ON p.PAT_ID = @PAT_ID
        AND op.PAT_ID = p.PAT_ID
    LEFT JOIN CLARITY_EAP eap
        ON eap.PROC_ID = op.PROC_ID
WHERE
    op.ORDER_TIME >= DATEADD(DAY, -@Days, GETDATE())
    AND eap.PROC_CAT_ID IN (
        SELECT PROC_CAT_ID FROM CLARITY_EAP_CAT
        WHERE PROC_CAT_NAME IN ('Anatomic Pathology', 'Surgical Pathology', 'Cytology', 'Pathology')
    )
    AND EXISTS (
        SELECT 1 FROM ORDER_RESULTS orr WHERE orr.ORDER_PROC_ID = op.ORDER_PROC_ID
    )
ORDER BY op.ORDER_TIME DESC;

/*
 * ALTERNATIVE for narrative pathology reports stored as free text:
 *
 * SELECT
 *     rec.REC_ID AS ReportID, @PAT_ID AS PatientID,
 *     COALESCE(rec.RECORD_TYPE, 'PATHOLOGY SURGICAL') AS ProcedureName,
 *     CONVERT(DATE, rec.SERV_DATE) AS OrderDate,
 *     rec.REPORT_TEXT AS ReportText
 * FROM DOCS_RCVD rec
 *     JOIN PATIENT p ON p.PAT_ID = @PAT_ID AND rec.PAT_ID = p.PAT_ID
 * WHERE rec.RECORD_TYPE LIKE '%PATHOLOG%'
 *   AND rec.SERV_DATE >= DATEADD(DAY, -@Days, GETDATE())
 *   AND rec.REPORT_TEXT IS NOT NULL;
 */


/* ============================================================
 * 3. RADIOLOGY REPORTS
 * Output file: radiology_reports.csv
 * Columns: ReportID, PatientID, ProcedureName, OrderDate, ReportText
 *
 * Covers: CT, MRI, PET, PET-CT, Ultrasound
 * ============================================================ */
SELECT
    op.ORDER_PROC_ID                            AS ReportID,
    @PAT_ID                                     AS PatientID,
    COALESCE(eap.PROC_NAME, 'Imaging Study')    AS ProcedureName,
    CONVERT(DATE, op.ORDER_TIME)                AS OrderDate,
    -- Combine impression + full narrative
    ISNULL(
        (
            SELECT ISNULL(orr.ORD_VALUE, '') + CHAR(10)
            FROM ORDER_RESULTS orr
            WHERE orr.ORDER_PROC_ID = op.ORDER_PROC_ID
            ORDER BY orr.LINE
            FOR XML PATH(''), TYPE
        ).value('(./text())[1]', 'NVARCHAR(MAX)'),
        ''
    )                                           AS ReportText
FROM ORDER_PROC op
    JOIN PATIENT p
        ON p.PAT_ID = @PAT_ID
        AND op.PAT_ID = p.PAT_ID
    LEFT JOIN CLARITY_EAP eap
        ON eap.PROC_ID = op.PROC_ID
WHERE
    op.ORDER_TIME >= DATEADD(DAY, -@Days, GETDATE())
    AND (
        eap.PROC_CAT_ID IN (
            SELECT PROC_CAT_ID FROM CLARITY_EAP_CAT
            WHERE PROC_CAT_NAME IN ('Radiology', 'Diagnostic Imaging', 'Nuclear Medicine',
                                     'Ultrasound', 'CT', 'MRI', 'PET Scan')
        )
        OR eap.PROC_NAME LIKE 'CT %'
        OR eap.PROC_NAME LIKE 'MR%'
        OR eap.PROC_NAME LIKE 'PET%'
        OR eap.PROC_NAME LIKE 'US %'
        OR eap.PROC_NAME LIKE '% ULTRASOUND%'
    )
    AND EXISTS (
        SELECT 1 FROM ORDER_RESULTS orr WHERE orr.ORDER_PROC_ID = op.ORDER_PROC_ID
    )
ORDER BY op.ORDER_TIME DESC;


/* ============================================================
 * 4. LAB RESULTS
 * Output file: lab_results.csv
 * Columns: ResultID, PatientID, ComponentName, OrderDate,
 *          ResultValue, ResultUnit, ReferenceRange, AbnormalFlag
 *
 * ResultID format: {ORDER_PROC_ID}|{COMPONENT_ID} (matches existing exports)
 * Focus: tumor markers (CA-125, HE4, hCG, CEA, AFP, LDH), CBC, CMP
 * ============================================================ */
SELECT
    CAST(orr.ORDER_PROC_ID AS VARCHAR(20)) + '|' +
        CAST(orr.COMPONENT_ID AS VARCHAR(20))   AS ResultID,
    @PAT_ID                                     AS PatientID,
    COALESCE(cc.NAME, cc.COMPONENT_ABBR, '')    AS ComponentName,
    CONVERT(DATE, op.ORDER_TIME)                AS OrderDate,
    ISNULL(orr.ORD_VALUE, '')                   AS ResultValue,
    ISNULL(orr.REF_UNIT, '')                    AS ResultUnit,
    ISNULL(orr.REFERENCE_RANGE, '')             AS ReferenceRange,
    ISNULL(orr.ABN_FLAG_C_NAME, '')             AS AbnormalFlag
FROM ORDER_RESULTS orr
    JOIN ORDER_PROC op
        ON op.ORDER_PROC_ID = orr.ORDER_PROC_ID
    JOIN PATIENT p
        ON p.PAT_ID = @PAT_ID
        AND op.PAT_ID = p.PAT_ID
    LEFT JOIN CLARITY_COMPONENT cc
        ON cc.COMPONENT_ID = orr.COMPONENT_ID
WHERE
    op.ORDER_TIME >= DATEADD(DAY, -@Days, GETDATE())
    AND orr.RESULT_STATUS_C = 3              -- Final result only
    AND orr.ORD_VALUE IS NOT NULL
    AND (
        -- Tumor markers
        cc.NAME LIKE '%CA-125%' OR cc.NAME LIKE '%CA125%'
        OR cc.NAME LIKE '%HE4%'
        OR cc.NAME LIKE '%HCG%' OR cc.NAME LIKE '%HUMAN CHORIONIC%'
        OR cc.NAME LIKE '%CEA%' OR cc.NAME LIKE '%CARCINOEMBRYONIC%'
        OR cc.NAME LIKE '%AFP%' OR cc.NAME LIKE '%ALPHA-FETO%'
        OR cc.NAME LIKE '%LDH%' OR cc.NAME LIKE '%LACTATE DEHYDROGENASE%'
        OR cc.NAME LIKE '%INHIBIN%'
        OR cc.NAME LIKE '%SCC ANTIGEN%'
        -- CBC
        OR cc.NAME LIKE '%WBC%' OR cc.NAME LIKE '%WHITE BLOOD%'
        OR cc.NAME LIKE '%HEMOGLOBIN%' OR cc.NAME = 'HGB'
        OR cc.NAME LIKE '%PLATELET%'
        OR cc.NAME LIKE '%NEUTROPHIL%'
        OR cc.NAME LIKE '%ABSOLUTE AUTO%'   -- automated differentials (matches your data: BASOPHIL ABSOLUTE AUTO)
        OR cc.NAME LIKE '%BASOPHIL%'
        OR cc.NAME LIKE '%EOSINOPHIL%'
        OR cc.NAME LIKE '%LYMPHOCYTE%'
        OR cc.NAME LIKE '%MONOCYTE%'
        -- CMP / metabolic
        OR cc.NAME LIKE '%CREATININE%'
        OR cc.NAME LIKE '%EGFR%'
        OR cc.NAME LIKE '%ALT%' OR cc.NAME LIKE '%ALANINE%'
        OR cc.NAME LIKE '%AST%' OR cc.NAME LIKE '%ASPARTATE%'
        OR cc.NAME LIKE '%BILIRUBIN%'
        OR cc.NAME LIKE '%ALBUMIN%'
        OR cc.NAME LIKE '%SODIUM%' OR cc.NAME = 'NA'
        OR cc.NAME LIKE '%POTASSIUM%' OR cc.NAME = 'K'
        OR cc.NAME LIKE '%MAGNESIUM%'
    )
ORDER BY op.ORDER_TIME DESC, orr.COMPONENT_ID;


/* ============================================================
 * 5. CANCER STAGING
 * Output file: cancer_staging.csv
 * Columns: PatientID, StageDate, StagingSystem, TNM_T, TNM_N, TNM_M,
 *          StageGroup, FIGOStage
 *
 * NOTE: FIGOStage in your exports uses format "FIGO Stage IIIC"
 * Two rows per staging event are common (one per staging category record).
 * ============================================================ */
SELECT
    @PAT_ID                                     AS PatientID,
    CONVERT(DATE, tm.STAGE_DATE)                AS StageDate,
    ISNULL(tm.SCHEMA_NAME, 'AJCC')              AS StagingSystem,
    ISNULL(tm.CLIN_T_NAME, '')                  AS TNM_T,
    ISNULL(tm.CLIN_N_NAME, '')                  AS TNM_N,
    ISNULL(tm.CLIN_M_NAME, '')                  AS TNM_M,
    ISNULL(tm.STAGE_GROUP, '')                  AS StageGroup,
    ISNULL(
        (
            SELECT TOP 1 tme.DISPLAY_NAME
            FROM TUMOR_REG_STAGING_ELEM tme
            WHERE tme.SUMMARY_ID = tm.SUMMARY_ID
              AND tme.ELEM_NAME LIKE '%FIGO%'
        ),
        ''
    )                                           AS FIGOStage
FROM TUMOR_STAGE_SUMMARY tm
    JOIN PATIENT p
        ON p.PAT_ID = @PAT_ID
        AND tm.PAT_ID = p.PAT_ID
WHERE
    tm.STAGE_DATE IS NOT NULL
ORDER BY tm.STAGE_DATE DESC;

/*
 * ALTERNATIVE — if TUMOR_STAGE_SUMMARY is not available,
 * FIGO stage is often in SmartForm data (EPIC_FHIR_FORM / SMARTDATA):
 *
 * SELECT @PAT_ID AS PatientID,
 *     CONVERT(DATE, smd.ENTRY_DATE) AS StageDate,
 *     'FIGO' AS StagingSystem, '' AS TNM_T, '' AS TNM_N, '' AS TNM_M,
 *     '' AS StageGroup,
 *     'FIGO Stage ' + smd.STRING_VALUE AS FIGOStage
 * FROM SMRTDTA_ELEM_VALUE smd
 *     JOIN PATIENT p ON p.PAT_ID = @PAT_ID AND smd.PAT_ID = p.PAT_ID
 * WHERE smd.ELEMENT_ID IN (
 *     SELECT HLV_ID FROM HLV_SMRTDTA_ELEM
 *     WHERE HLV_CONCEPTNAME LIKE '%FIGO%'
 * );
 */


/* ============================================================
 * 6. MEDICATIONS
 * Output file: medications.csv
 * Columns: PatientID, MedicationName, StartDate, EndDate,
 *          Route, Dose, Frequency, OrderClass
 *
 * NOTE: Dose format in your exports: "673.000 mg" (number + unit combined)
 * OrderClass: "Chemotherapy" for chemo agents
 * ============================================================ */
SELECT
    @PAT_ID                                         AS PatientID,
    cm.NAME                                         AS MedicationName,
    CONVERT(DATE, om.START_DATE)                    AS StartDate,
    CONVERT(DATE, om.END_DATE)                      AS EndDate,
    ISNULL(roa.NAME, '')                            AS Route,
    -- Reproduce the "673.000 mg" format seen in your exports
    CASE
        WHEN om.DOSE_UNIT_C IS NOT NULL
            THEN CAST(CAST(om.MIN_DISCRETE_DOSE AS DECIMAL(12,3)) AS VARCHAR(20))
                 + ' ' + ISNULL(du.ABBR, '')
        ELSE ''
    END                                             AS Dose,
    ISNULL(freq.NAME, CAST(om.FREQ_ID AS VARCHAR(10)), '') AS Frequency,
    ISNULL(oc.NAME, 'Medications')                  AS OrderClass
FROM ORDER_MED om
    JOIN PATIENT p
        ON p.PAT_ID = @PAT_ID
        AND om.PAT_ID = p.PAT_ID
    LEFT JOIN CLARITY_MEDICATION cm
        ON cm.MEDICATION_ID = om.MEDICATION_ID
    LEFT JOIN ZC_ADMIN_ROUTE roa
        ON roa.ADMIN_ROUTE_C = om.ADMIN_ROUTE_C
    LEFT JOIN ZC_DOSE_UNIT du
        ON du.DOSE_UNIT_C = om.DOSE_UNIT_C
    LEFT JOIN ZC_FREQ freq
        ON freq.FREQ_ID = om.FREQ_ID
    LEFT JOIN ZC_MED_ORDER_CLASS oc
        ON oc.MED_ORDER_CLASS_C = om.MED_ORDER_CLASS_C
WHERE
    om.START_DATE >= DATEADD(DAY, -@Days, GETDATE())
    AND om.ORDER_STATUS_C NOT IN (4, 7)   -- exclude Canceled (4), Voided (7)
    AND (
        oc.NAME IN ('Chemotherapy', 'Outpatient Chemotherapy',
                    'Prescription Medications', 'Medications', 'Immunotherapy')
        OR cm.PHARMACY_CLASS LIKE '%ANTINEOPLAS%'
        OR cm.PHARMACY_CLASS LIKE '%IMMUNOSUPPRESS%'
        OR cm.NAME LIKE '%CARBOPLATIN%'
        OR cm.NAME LIKE '%PACLITAXEL%'
        OR cm.NAME LIKE '%BEVACIZUMAB%'
        OR cm.NAME LIKE '%OLAPARIB%'
        OR cm.NAME LIKE '%NIRAPARIB%'
        OR cm.NAME LIKE '%PEMBROLIZUMAB%'
        OR cm.NAME LIKE '%DOSTARLIMAB%'
        OR cm.NAME LIKE '%GEMCITABINE%'
        OR cm.NAME LIKE '%CISPLATIN%'
        OR cm.NAME LIKE '%DOXORUBICIN%'
        OR cm.NAME LIKE '%TOPOTECAN%'
    )
ORDER BY om.START_DATE DESC;


/* ============================================================
 * 7. DIAGNOSES
 * Output file: diagnoses.csv
 * Columns: PatientID, DiagnosisName, ICD10Code, DateOfEntry, Status
 *
 * NOTE: Status column is empty in your real exports (empty string) —
 * the accessor handles this. Include GYN + relevant comorbidities.
 * ============================================================ */
SELECT
    @PAT_ID                                     AS PatientID,
    edg.DX_NAME                                 AS DiagnosisName,
    ISNULL(edg.ICD10_CODE, '')                  AS ICD10Code,
    CONVERT(DATE, pl.NOTED_DATE)                AS DateOfEntry,
    ISNULL(zs.NAME, '')                         AS Status
FROM PAT_PROBLEM_LIST pl
    JOIN PATIENT p
        ON p.PAT_ID = @PAT_ID
        AND pl.PAT_ID = p.PAT_ID
    LEFT JOIN CLARITY_EDG edg
        ON edg.DX_ID = pl.DX_ID
    LEFT JOIN ZC_PROBLEM_STATUS zs
        ON zs.PROBLEM_STATUS_C = pl.PROBLEM_STATUS_C
WHERE
    pl.NOTED_DATE IS NOT NULL
    AND pl.PROBLEM_STATUS_C != 3                -- exclude Deleted
ORDER BY pl.NOTED_DATE DESC;


/* ============================================================
 * UTILITY: Find PAT_ID (UUID) by MRN
 * Run this first to get @PAT_ID for each patient
 * ============================================================ */
/*
SELECT
    p.PAT_ID        AS PAT_ID,       -- Use this as @PAT_ID and folder name
    ii.IDENTITY_ID  AS MRN,
    p.PAT_NAME      AS Name,
    p.BIRTH_DATE    AS DOB,
    p.SEX_C         AS Sex
FROM PATIENT p
    JOIN IDENTITY_ID ii
        ON ii.PAT_ID = p.PAT_ID
        AND ii.IDENTITY_TYPE_ID = 105   -- 105 = MRN type at most Epic installs
                                         -- adjust if your MRN identity type differs
WHERE
    ii.IDENTITY_ID IN (
        '1234567',
        '2345678',
        '3456789',
        '4567890'
        -- add your 10 MRNs here
    );
*/

/* ============================================================
 * EXPORT CHECKLIST
 *
 * For each patient:
 *   [ ] Set @PAT_ID = '<UUID from utility query above>'
 *   [ ] Run block 1 → save as clinical_notes.csv
 *   [ ] Run block 2 → save as pathology_reports.csv  (OK if 0 rows)
 *   [ ] Run block 3 → save as radiology_reports.csv   (OK if 0 rows)
 *   [ ] Run block 4 → save as lab_results.csv
 *   [ ] Run block 5 → save as cancer_staging.csv
 *   [ ] Run block 6 → save as medications.csv
 *   [ ] Run block 7 → save as diagnoses.csv
 *   [ ] Drop all 7 files into infra/patient_data/<PAT_ID>/
 *   [ ] Run: python3 scripts/validate_patient_csvs.py --patient <PAT_ID>
 *
 * ENCODING: UTF-8 (SSMS exports UTF-16 by default — change in save dialog)
 * SSMS shortcut: Results → Right-click → Save Results As → CSV → encoding dropdown
 * OR use sqlcmd: sqlcmd -S server -d db -E -Q "..." -o file.csv -s "," -W
 * ============================================================ */
