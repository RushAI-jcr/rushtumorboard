import React from 'react';
import { makeStyles, Text, tokens, mergeClasses } from '@fluentui/react-components';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useSelector } from 'react-redux';
import type { Message } from '../types';
import { RootState } from '../store/store';
import { getAgentMeta, getAgentLabel, getAgentColor, translateErrorMessages, WORKFLOW_STEPS } from '../utils/agentMeta';

// Add global animations via style tag
const AnimationStyles = () => (
  <style>
    {`
    @keyframes pulseDot1 {
      0% { opacity: 0.3; transform: translateY(0px); }
      50% { opacity: 1; transform: translateY(-1px); }
      100% { opacity: 0.3; transform: translateY(0px); }
    }
    @keyframes pulseDot2 {
      0% { opacity: 0.3; transform: translateY(0px); }
      50% { opacity: 1; transform: translateY(-1px); }
      100% { opacity: 0.3; transform: translateY(0px); }
    }
    @keyframes pulseDot3 {
      0% { opacity: 0.3; transform: translateY(0px); }
      50% { opacity: 1; transform: translateY(-1px); }
      100% { opacity: 0.3; transform: translateY(0px); }
    }
    .dot1, .dot2, .dot3 {
      display: inline-block;
      width: 2px;
      height: 2px;
      border-radius: 50%;
      background-color: #333;
      margin: 0 2px;
    }
    .dot1 { animation: pulseDot1 1.4s infinite ease-in-out; }
    .dot2 { animation: pulseDot2 1.4s infinite ease-in-out 0.2s; }
    .dot3 { animation: pulseDot3 1.4s infinite ease-in-out 0.4s; }
    `}
  </style>
);

const useStyles = makeStyles({
    container: {
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
        padding: '1rem',
    },
    messageGroupLeft: {
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '90%',
        alignSelf: 'flex-start',
    },
    loadingDot: {
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '90%',
        alignSelf: 'flex-start',
        content: '""',
        width: '110px',
        height: '50px',
    },
    messageGroupRight: {
        display: 'flex',
        flexDirection: 'column',
        maxWidth: '90%',
        alignSelf: 'flex-end',
    },
    // Sender badge row
    senderRow: {
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        marginBottom: '4px',
        paddingLeft: '0.5rem',
    },
    senderIcon: {
        fontSize: '14px',
    },
    senderBadge: {
        fontSize: tokens.fontSizeBase200,
        fontWeight: '600',
        padding: '1px 8px',
        borderRadius: '10px',
        color: 'white',
        lineHeight: '1.5',
    },
    senderPlain: {
        fontSize: tokens.fontSizeBase200,
        color: tokens.colorNeutralForeground3,
    },
    message: {
        padding: '0.75rem 1rem',
        borderRadius: '12px',
        width: 'fit-content',
        maxWidth: '100%',
        wordWrap: 'break-word',
    },
    userMessage: {
        backgroundColor: tokens.colorBrandBackground,
        color: tokens.colorNeutralForegroundInverted,
        borderTopRightRadius: '4px',
    },
    botMessage: {
        backgroundColor: tokens.colorNeutralBackground4,
        color: tokens.colorNeutralForeground1,
        borderTopLeftRadius: '4px',
    },
    loadingMessage: {
        borderRadius: '12px',
        width: 'fit-content',
        maxWidth: '100%',
        wordWrap: 'break-word',
        backgroundColor: tokens.colorNeutralBackground4,
        height: '80%',
        padding: '0.5rem 0.75rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
    },
    loadingDots: {
        display: 'flex',
        alignItems: 'center',
        gap: '2px',
    },
    // Progress bar
    progressContainer: {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '8px 12px',
        backgroundColor: tokens.colorNeutralBackground3,
        borderRadius: '8px',
        marginBottom: '0.5rem',
        alignSelf: 'flex-start',
        maxWidth: '90%',
    },
    progressText: {
        fontSize: tokens.fontSizeBase200,
        color: tokens.colorNeutralForeground2,
        fontWeight: '500',
    },
    progressBar: {
        flex: 1,
        height: '4px',
        backgroundColor: tokens.colorNeutralBackground5,
        borderRadius: '2px',
        overflow: 'hidden',
        minWidth: '100px',
    },
    progressFill: {
        height: '100%',
        borderRadius: '2px',
        transition: 'width 0.5s ease-in-out',
    },
    markdownContainer: {
        '& p': {
            margin: '0 0 0.75rem 0',
            '&:last-child': { marginBottom: 0 },
        },
        '& h1, & h2, & h3, & h4, & h5, & h6': {
            marginTop: '0.5rem',
            marginBottom: '0.5rem',
        },
        '& ul, & ol': {
            paddingLeft: '1.5rem',
            marginBottom: '0.75rem',
        },
        '& code': {
            backgroundColor: 'rgba(0, 0, 0, 0.1)',
            padding: '0.1rem 0.2rem',
            borderRadius: '3px',
            fontFamily: 'monospace',
        },
        '& pre': {
            backgroundColor: 'rgba(0, 0, 0, 0.1)',
            padding: '0.5rem',
            borderRadius: '4px',
            overflowX: 'auto',
            '& code': { backgroundColor: 'transparent', padding: 0 },
        },
        '& blockquote': {
            marginLeft: '0.5rem',
            paddingLeft: '0.5rem',
            borderLeft: '4px solid rgba(0, 0, 0, 0.2)',
            color: 'rgba(0, 0, 0, 0.7)',
        },
        '& a': {
            color: 'inherit',
            textDecoration: 'underline',
        },
        '& table': {
            borderCollapse: 'collapse',
            width: '100%',
            margin: '0.75rem 0',
            '& th, & td': {
                border: '1px solid rgba(0, 0, 0, 0.2)',
                padding: '0.3rem 0.5rem',
                textAlign: 'left',
            },
            '& th': { backgroundColor: 'rgba(0, 0, 0, 0.1)' },
        },
    },
    userMarkdownContainer: {
        '& blockquote': {
            borderLeftColor: 'rgba(255, 255, 255, 0.4)',
            color: 'rgba(255, 255, 255, 0.8)',
        },
        '& code, & pre': { backgroundColor: 'rgba(255, 255, 255, 0.2)' },
        '& a': { color: 'inherit' },
        '& table th, & table td': { border: '1px solid rgba(255, 255, 255, 0.3)' },
        '& table th': { backgroundColor: 'rgba(255, 255, 255, 0.2)' },
    },
});

const LoadingDots = () => {
    const styles = useStyles();
    return (
        <div className={styles.loadingDots}>
            <span className="dot1"></span>
            <span className="dot2"></span>
            <span className="dot3"></span>
        </div>
    );
};

/** Render the sender badge with icon and color. */
function SenderBadge({ sender, isBot }: { sender: string; isBot: boolean }) {
    const styles = useStyles();
    if (!isBot) {
        return (
            <div className={styles.senderRow}>
                <Text className={styles.senderPlain}>{sender || 'You'}</Text>
            </div>
        );
    }
    const meta = getAgentMeta(sender);
    const label = getAgentLabel(sender);
    const color = getAgentColor(sender);
    return (
        <div className={styles.senderRow}>
            <span className={styles.senderIcon}>{meta?.icon ?? '🤖'}</span>
            <span className={styles.senderBadge} style={{ backgroundColor: color }}>
                {label}
            </span>
        </div>
    );
}

/** Infer how far through the workflow we are based on which agents have responded. */
function WorkflowProgress({ messages }: { messages: Message[] }) {
    const styles = useStyles();
    // Collect all agent senders from bot messages
    const respondedAgents = new Set<string>();
    for (const msg of messages) {
        if (msg.isBot && msg.sender) {
            respondedAgents.add(msg.sender);
        }
    }

    // Find the highest completed step
    let completedSteps = 0;
    for (const step of WORKFLOW_STEPS) {
        if (respondedAgents.has(step.id)) {
            completedSteps = (step.step ?? 0) + 1;
        }
    }

    if (completedSteps === 0) return null;

    const totalSteps = WORKFLOW_STEPS.length;
    const pct = Math.round((completedSteps / totalSteps) * 100);

    // Find current step label
    const currentStep = WORKFLOW_STEPS.find(s => (s.step ?? 0) === completedSteps - 1);
    const nextStep = WORKFLOW_STEPS.find(s => (s.step ?? 0) === completedSteps);

    const statusText = completedSteps >= totalSteps
        ? 'All steps complete'
        : `Step ${completedSteps} of ${totalSteps}: ${currentStep?.label ?? ''} done${nextStep ? ` — next: ${nextStep.label}` : ''}`;

    return (
        <div className={styles.progressContainer}>
            <Text className={styles.progressText}>{statusText}</Text>
            <div className={styles.progressBar}>
                <div
                    className={styles.progressFill}
                    style={{
                        width: `${pct}%`,
                        backgroundColor: completedSteps >= totalSteps ? '#107C10' : '#0078D4',
                    }}
                />
            </div>
        </div>
    );
}

interface MessageListProps {
    messages: Message[];
}

export default function MessageList({ messages }: MessageListProps) {
    const styles = useStyles();
    const isLoading = useSelector((state: RootState) => state.chat.isLoading);
    const pendingResponses = useSelector((state: RootState) => state.chat.pendingResponses);

    // Process message content to handle special formatting + error translation
    const renderMessageContent = (content: string, isBot: boolean) => {
        if (!content || typeof content !== 'string') return '';

        // Translate ERROR_TYPE codes for bot messages
        const processed = isBot ? translateErrorMessages(content) : content;

        return (
            <div className={mergeClasses(
                styles.markdownContainer,
                !isBot ? styles.userMarkdownContainer : undefined,
            )}>
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                        a: ({ node, ...props }) => (
                            <a {...props} target="_blank" rel="noopener noreferrer" />
                        ),
                    }}
                >
                    {processed}
                </ReactMarkdown>
            </div>
        );
    };

    return (
        <div className={styles.container}>
            <AnimationStyles />

            {/* Progress indicator — shows once agents start responding */}
            {messages && messages.length > 0 && (
                <WorkflowProgress messages={messages} />
            )}

            {/* Render all regular messages */}
            {messages && messages.map(message => {
                if (!message || typeof message !== 'object') return null;
                const isBot = message.isBot === true;

                return (
                    <div
                        key={message.id || `msg-${Math.random()}`}
                        className={isBot ? styles.messageGroupLeft : styles.messageGroupRight}
                    >
                        <SenderBadge sender={message.sender || ''} isBot={isBot} />
                        <div
                            className={mergeClasses(
                                styles.message,
                                isBot ? styles.botMessage : styles.userMessage,
                            )}
                        >
                            {renderMessageContent(message.content || '', isBot)}
                        </div>
                    </div>
                );
            })}

            {/* Render loading indicators for each pending response */}
            {isLoading === true && pendingResponses && Array.isArray(pendingResponses) && pendingResponses.length > 0 &&
                pendingResponses.map((pendingResponse, index) => {
                    if (!pendingResponse) return null;
                    const agent = pendingResponse.targetAgent || 'Orchestrator';
                    return (
                        <div key={`loading-${index}`} className={styles.loadingDot}>
                            <SenderBadge sender={agent} isBot={true} />
                            <div className={styles.loadingMessage}>
                                <LoadingDots />
                            </div>
                        </div>
                    );
                })
            }

            {/* Fallback loading indicator */}
            {isLoading === true && (!pendingResponses || !Array.isArray(pendingResponses) || pendingResponses.length === 0) && (
                <div className={styles.loadingDot}>
                    <SenderBadge sender="Orchestrator" isBot={true} />
                    <div className={styles.loadingMessage}>
                        <LoadingDots />
                    </div>
                </div>
            )}
        </div>
    );
}
