import React, { useState, useEffect, useRef } from 'react';
import {
    makeStyles,
    tokens,
    Portal,
    Text,
} from '@fluentui/react-components';
import { getAgentMeta } from '../utils/agentMeta';

const useStyles = makeStyles({
    menuContainer: {
        position: 'absolute',
        zIndex: 100,
        width: '300px',
        boxShadow: tokens.shadow16,
        borderRadius: tokens.borderRadiusMedium,
        backgroundColor: tokens.colorNeutralBackground1,
        border: `1px solid ${tokens.colorNeutralStroke1}`,
        overflow: 'hidden',
        maxHeight: '320px',
        overflowY: 'auto',
    },
    menuHeader: {
        padding: '6px 12px',
        fontSize: tokens.fontSizeBase100,
        color: tokens.colorNeutralForeground3,
        borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
        backgroundColor: tokens.colorNeutralBackground3,
    },
    menuItem: {
        padding: '8px 12px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        '&:hover': {
            backgroundColor: tokens.colorNeutralBackground2,
        },
    },
    selectedItem: {
        backgroundColor: tokens.colorBrandBackground,
        color: tokens.colorNeutralForegroundOnBrand,
        '&:hover': {
            backgroundColor: tokens.colorBrandBackgroundHover,
        },
    },
    agentIcon: {
        fontSize: '18px',
        width: '24px',
        textAlign: 'center' as const,
        flexShrink: 0,
    },
    agentInfo: {
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
    },
    agentLabel: {
        fontWeight: '600',
        fontSize: tokens.fontSizeBase200,
        lineHeight: '1.3',
    },
    agentDesc: {
        fontSize: tokens.fontSizeBase100,
        opacity: 0.75,
        lineHeight: '1.3',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
    },
    selectedDesc: {
        opacity: 0.85,
    },
});

interface MentionAutocompleteProps {
    agents: string[];
    textAreaRef: React.RefObject<HTMLInputElement | HTMLTextAreaElement>;
    isOpen: boolean;
    onSelect: (agent: string) => void;
    onClose: () => void;
    position: { top: number; left: number };
    query: string;
}

const MentionAutocomplete: React.FC<MentionAutocompleteProps> = ({
    agents,
    isOpen,
    onSelect,
    onClose,
    position,
    query
}) => {
    const styles = useStyles();
    const menuRef = useRef<HTMLDivElement>(null);
    const [selectedIndex, setSelectedIndex] = useState(0);
    const [filteredAgents, setFilteredAgents] = useState<string[]>(agents);
    const [menuPosition, setMenuPosition] = useState({ top: 0, left: 0 });

    // Calculate position - show dropdown ABOVE the cursor position
    useEffect(() => {
        const itemHeight = 48; // Taller items with descriptions
        const headerHeight = 28;
        const numItems = Math.min(filteredAgents.length, 6);
        const menuHeight = numItems * itemHeight + headerHeight;

        setMenuPosition({
            top: position.top - menuHeight,
            left: Math.min(position.left, window.innerWidth - 320),
        });
    }, [position, filteredAgents.length]);

    // Filter agents based on query — match against both ID and label
    useEffect(() => {
        if (query) {
            const q = query.toLowerCase();
            const filtered = agents.filter(agent => {
                const meta = getAgentMeta(agent);
                return agent.toLowerCase().includes(q)
                    || (meta?.label.toLowerCase().includes(q))
                    || (meta?.description.toLowerCase().includes(q));
            });
            setFilteredAgents(filtered);
            setSelectedIndex(0);
        } else {
            setFilteredAgents(agents);
        }
    }, [agents, query]);

    // Handle click outside to close the menu
    useEffect(() => {
        if (!isOpen) return;

        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                onClose();
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen, onClose]);

    // Handle keyboard navigation
    useEffect(() => {
        if (!isOpen) return;

        const handleKeyDown = (e: KeyboardEvent) => {
            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    setSelectedIndex(prev => (prev + 1) % filteredAgents.length);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    setSelectedIndex(prev => (prev - 1 + filteredAgents.length) % filteredAgents.length);
                    break;
                case 'Enter':
                    e.preventDefault();
                    if (filteredAgents.length > 0) {
                        onSelect(filteredAgents[selectedIndex]);
                    }
                    break;
                case 'Escape':
                    e.preventDefault();
                    onClose();
                    break;
                default:
                    break;
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [isOpen, selectedIndex, filteredAgents, onSelect, onClose]);

    if (!isOpen || filteredAgents.length === 0) {
        return null;
    }

    return (
        <Portal>
            <div
                ref={menuRef}
                className={styles.menuContainer}
                style={{
                    top: menuPosition.top,
                    left: menuPosition.left,
                }}
            >
                <div className={styles.menuHeader}>
                    Select an agent
                </div>
                {filteredAgents.map((agent, index) => {
                    const meta = getAgentMeta(agent);
                    const isSelected = index === selectedIndex;
                    return (
                        <div
                            key={agent}
                            className={`${styles.menuItem} ${isSelected ? styles.selectedItem : ''}`}
                            onClick={() => onSelect(agent)}
                        >
                            <span className={styles.agentIcon}>{meta?.icon ?? '🤖'}</span>
                            <div className={styles.agentInfo}>
                                <Text className={styles.agentLabel}>
                                    {meta?.label ?? agent}
                                </Text>
                                <Text className={`${styles.agentDesc} ${isSelected ? styles.selectedDesc : ''}`}>
                                    {meta?.description ?? ''}
                                </Text>
                            </div>
                        </div>
                    );
                })}
            </div>
        </Portal>
    );
};

export default MentionAutocomplete;
