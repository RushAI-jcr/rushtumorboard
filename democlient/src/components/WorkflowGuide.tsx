import {
    makeStyles,
    tokens,
    Dialog,
    DialogTrigger,
    DialogSurface,
    DialogBody,
    DialogTitle,
    DialogContent,
    Button,
    Text,
    Divider,
    Badge,
} from '@fluentui/react-components';
import { Dismiss24Regular, Info24Regular } from '@fluentui/react-icons';

const useStyles = makeStyles({
    surface: {
        maxWidth: '640px',
        maxHeight: '85vh',
    },
    content: {
        overflowY: 'auto',
        paddingBottom: '1rem',
    },
    subtitle: {
        color: tokens.colorNeutralForeground3,
        marginBottom: '1rem',
        display: 'block',
    },
    section: {
        marginBottom: '1.5rem',
    },
    sectionTitle: {
        fontWeight: 'bold',
        fontSize: tokens.fontSizeBase400,
        marginBottom: '0.5rem',
        display: 'block',
    },
    stepList: {
        listStyleType: 'none',
        padding: 0,
        margin: 0,
    },
    step: {
        display: 'flex',
        gap: '0.75rem',
        padding: '0.6rem 0',
        alignItems: 'flex-start',
    },
    stepNumber: {
        minWidth: '28px',
        height: '28px',
        borderRadius: '50%',
        backgroundColor: tokens.colorBrandBackground,
        color: tokens.colorNeutralForegroundOnBrand,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 'bold',
        fontSize: tokens.fontSizeBase200,
        flexShrink: 0,
    },
    stepContent: {
        flex: 1,
    },
    stepTitle: {
        fontWeight: '600',
        display: 'block',
        marginBottom: '2px',
    },
    stepDesc: {
        color: tokens.colorNeutralForeground3,
        fontSize: tokens.fontSizeBase200,
        display: 'block',
    },
    quickStart: {
        backgroundColor: tokens.colorNeutralBackground3,
        borderRadius: '8px',
        padding: '1rem',
        marginBottom: '1.5rem',
    },
    commandExample: {
        fontFamily: 'monospace',
        backgroundColor: tokens.colorNeutralBackground1,
        padding: '0.5rem 0.75rem',
        borderRadius: '4px',
        display: 'block',
        margin: '0.5rem 0',
        fontSize: tokens.fontSizeBase300,
        border: `1px solid ${tokens.colorNeutralStroke1}`,
    },
    tip: {
        display: 'flex',
        gap: '0.5rem',
        alignItems: 'flex-start',
        backgroundColor: '#fff8e1',
        padding: '0.75rem',
        borderRadius: '6px',
        marginTop: '0.5rem',
        fontSize: tokens.fontSizeBase200,
    },
    outputList: {
        margin: '0.5rem 0',
        paddingLeft: '1.25rem',
    },
    outputItem: {
        padding: '0.2rem 0',
        fontSize: tokens.fontSizeBase200,
    },
    closeButton: {
        position: 'absolute' as const,
        top: '12px',
        right: '12px',
    },
    headerRow: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
    },
});

interface WorkflowGuideProps {
    open: boolean;
    onClose: () => void;
}

export default function WorkflowGuide({ open, onClose }: WorkflowGuideProps) {
    const classes = useStyles();

    return (
        <Dialog open={open} onOpenChange={(_, data) => { if (!data.open) onClose(); }}>
            <DialogSurface className={classes.surface}>
                <DialogBody>
                    <div className={classes.headerRow}>
                        <DialogTitle>How the Tumor Board Assistant Works</DialogTitle>
                        <Button
                            appearance="subtle"
                            icon={<Dismiss24Regular />}
                            onClick={onClose}
                            aria-label="Close"
                        />
                    </div>
                    <DialogContent className={classes.content}>
                        <Text className={classes.subtitle}>
                            A step-by-step guide for preparing GYN Oncology tumor board cases
                        </Text>

                        {/* Quick Start */}
                        <div className={classes.quickStart}>
                            <Text className={classes.sectionTitle}>Quick Start</Text>
                            <Text style={{ display: 'block', marginBottom: '0.5rem' }}>
                                1. Click <strong>"New Chat"</strong> in the left sidebar
                            </Text>
                            <Text style={{ display: 'block', marginBottom: '0.5rem' }}>
                                2. Type this command and press Enter:
                            </Text>
                            <code className={classes.commandExample}>
                                @Orchestrator prepare tumor board for patient [Patient ID]
                            </code>
                            <Text style={{ display: 'block' }}>
                                3. Wait for the system to gather data and generate your report
                            </Text>
                        </div>

                        <Divider />

                        {/* What Happens Behind the Scenes */}
                        <div className={classes.section} style={{ marginTop: '1rem' }}>
                            <Text className={classes.sectionTitle}>
                                What Happens After You Send Your Message
                            </Text>
                            <Text className={classes.stepDesc} style={{ marginBottom: '0.75rem' }}>
                                The system uses specialized AI agents that work together automatically.
                                You do not need to run each step — just send the initial message and wait.
                            </Text>

                            <ol className={classes.stepList}>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>1</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>Pre-Meeting Checklist</Text>
                                        <Text className={classes.stepDesc}>
                                            Checks for missing or outdated data before starting. Flags anything that needs attention (e.g., missing labs, pending pathology).
                                        </Text>
                                    </div>
                                </li>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>2</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>Patient History</Text>
                                        <Text className={classes.stepDesc}>
                                            Pulls demographics, medical history, and clinical timeline from Epic/Caboodle records.
                                        </Text>
                                    </div>
                                </li>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>3</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>Oncologic History</Text>
                                        <Text className={classes.stepDesc}>
                                            Reviews prior cancer diagnoses, treatments, surgical history, and outside hospital transfers.
                                        </Text>
                                    </div>
                                </li>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>4</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>Pathology Review</Text>
                                        <Text className={classes.stepDesc}>
                                            Extracts histology, immunohistochemistry (IHC), and molecular markers (BRCA, MMR, p53, POLE).
                                        </Text>
                                    </div>
                                </li>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>5</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>Radiology Review</Text>
                                        <Text className={classes.stepDesc}>
                                            Summarizes CT, MRI, PET, and ultrasound findings with dates and measurements.
                                        </Text>
                                    </div>
                                </li>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>6</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>Current Status and Staging</Text>
                                        <Text className={classes.stepDesc}>
                                            Compiles FIGO staging, tumor markers (CA-125, HE4), and platinum sensitivity assessment.
                                        </Text>
                                    </div>
                                </li>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>7</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>NCCN Guidelines</Text>
                                        <Text className={classes.stepDesc}>
                                            Looks up current NCCN treatment recommendations based on the patient's cancer type and stage.
                                        </Text>
                                    </div>
                                </li>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>8</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>Clinical Trials</Text>
                                        <Text className={classes.stepDesc}>
                                            Searches ClinicalTrials.gov and NCI for open trials matching the patient's diagnosis and eligibility.
                                        </Text>
                                    </div>
                                </li>
                                <li className={classes.step}>
                                    <div className={classes.stepNumber}>9</div>
                                    <div className={classes.stepContent}>
                                        <Text className={classes.stepTitle}>Report Generation</Text>
                                        <Text className={classes.stepDesc}>
                                            Creates two downloadable files:
                                        </Text>
                                        <ul className={classes.outputList}>
                                            <li className={classes.outputItem}>
                                                <strong>Word Document (.docx)</strong> — Landscape one-page summary matching the Rush tumor board handout format (5 columns: patient info, diagnosis, treatments, imaging, discussion)
                                            </li>
                                            <li className={classes.outputItem}>
                                                <strong>PowerPoint (.pptx)</strong> — 5-slide presentation for display during the tumor board meeting
                                            </li>
                                        </ul>
                                    </div>
                                </li>
                            </ol>
                        </div>

                        <Divider />

                        {/* Tips */}
                        <div className={classes.section} style={{ marginTop: '1rem' }}>
                            <Text className={classes.sectionTitle}>Tips</Text>

                            <div className={classes.tip}>
                                <Badge appearance="filled" color="warning" size="small">Tip</Badge>
                                <Text>
                                    You can talk to individual agents directly using <strong>@AgentName</strong>.
                                    For example, <code>@ClinicalTrials find ovarian cancer trials accepting platinum-resistant patients</code>.
                                </Text>
                            </div>

                            <div className={classes.tip} style={{ marginTop: '0.5rem' }}>
                                <Badge appearance="filled" color="warning" size="small">Tip</Badge>
                                <Text>
                                    If the system flags missing data in Step 1, you may need to check that the patient's records are up to date in Epic before re-running.
                                </Text>
                            </div>

                            <div className={classes.tip} style={{ marginTop: '0.5rem' }}>
                                <Badge appearance="filled" color="warning" size="small">Tip</Badge>
                                <Text>
                                    Download links for the Word doc and PowerPoint appear at the end of the chat. Click them to save the files to your computer.
                                </Text>
                            </div>
                        </div>

                        <Divider />

                        {/* Available Agents */}
                        <div className={classes.section} style={{ marginTop: '1rem' }}>
                            <Text className={classes.sectionTitle}>Available Agents</Text>
                            <Text className={classes.stepDesc} style={{ marginBottom: '0.5rem' }}>
                                You can @mention any of these agents directly in the chat:
                            </Text>
                            <ul className={classes.outputList}>
                                <li className={classes.outputItem}><strong>@Orchestrator</strong> — Runs the full tumor board workflow start to finish</li>
                                <li className={classes.outputItem}><strong>@PatientHistory</strong> — Demographics and clinical timeline</li>
                                <li className={classes.outputItem}><strong>@OncologicHistory</strong> — Cancer diagnosis and treatment history</li>
                                <li className={classes.outputItem}><strong>@Pathology</strong> — Pathology and molecular markers</li>
                                <li className={classes.outputItem}><strong>@Radiology</strong> — Imaging findings</li>
                                <li className={classes.outputItem}><strong>@PatientStatus</strong> — Current staging and tumor markers</li>
                                <li className={classes.outputItem}><strong>@ClinicalGuidelines</strong> — NCCN treatment recommendations</li>
                                <li className={classes.outputItem}><strong>@ClinicalTrials</strong> — Open clinical trial search</li>
                                <li className={classes.outputItem}><strong>@MedicalResearch</strong> — PubMed literature review</li>
                                <li className={classes.outputItem}><strong>@ReportCreation</strong> — Generate Word doc and PowerPoint</li>
                            </ul>
                        </div>
                    </DialogContent>
                </DialogBody>
            </DialogSurface>
        </Dialog>
    );
}

/**
 * Inline guide shown in the empty chat panel before a chat is selected.
 */
export function InlineWorkflowHint() {
    const classes = useInlineStyles();
    return (
        <div className={classes.container}>
            <Text className={classes.title}>GYN Oncology Tumor Board Assistant</Text>
            <Text className={classes.desc}>
                Prepare a case in three steps:
            </Text>
            <ol className={classes.steps}>
                <li>Click <strong>New Chat</strong> in the sidebar</li>
                <li>Type: <code className={classes.code}>@Orchestrator prepare tumor board for patient [Patient ID]</code></li>
                <li>Wait for the agents to gather data and generate the Word doc and PowerPoint</li>
            </ol>
            <Text className={classes.hint}>
                Click <strong>"How It Works"</strong> in the header for the full guide.
            </Text>
        </div>
    );
}

const useInlineStyles = makeStyles({
    container: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        padding: '2rem',
        textAlign: 'center',
        maxWidth: '480px',
        margin: '0 auto',
    },
    title: {
        fontSize: tokens.fontSizeBase500,
        fontWeight: 'bold',
        marginBottom: '0.75rem',
    },
    desc: {
        color: tokens.colorNeutralForeground3,
        marginBottom: '0.75rem',
    },
    steps: {
        textAlign: 'left',
        lineHeight: '1.8',
        marginBottom: '1rem',
        paddingLeft: '1.25rem',
    },
    code: {
        fontFamily: 'monospace',
        backgroundColor: tokens.colorNeutralBackground3,
        padding: '2px 6px',
        borderRadius: '4px',
        fontSize: tokens.fontSizeBase200,
    },
    hint: {
        color: tokens.colorNeutralForeground3,
        fontSize: tokens.fontSizeBase200,
        marginTop: '0.5rem',
    },
});
