// Intent Detection System
// Automatically detects user intent from message

import { IntentType } from './types';

interface IntentPattern {
  intent: IntentType;
  patterns: RegExp[];
  keywords: string[];
}

const INTENT_PATTERNS: IntentPattern[] = [
  {
    intent: 'create_project',
    patterns: [
      /\b(create|build|make|develop|generate|start|banaye|banao|banayo)\b/i,
      /\b(app|website|project|tool|bot|page|component|feature)\b/i,
      /\b(with|and|using|including|saath|aur)\b/i
    ],
    keywords: ['create', 'build', 'make', 'app', 'website', 'project', 'banaye', 'banao']
  },
  {
    intent: 'fix_bug',
    patterns: [
      /\b(fix|debug|error|bug|issue|problem|repair|solve|sahi|thik|fix)\b/i,
      /\b(not working|broken|crash|fail|error|galat|kaam nhi)\b/i
    ],
    keywords: ['fix', 'debug', 'error', 'bug', 'issue', 'thik', 'sahi']
  },
  {
    intent: 'explore_code',
    patterns: [
      /\b(explore|analyze|explain|understand|review|check|dekh|samjho|padho)\b/i,
      /\b(code|file|function|component|module|what does|kya karta)\b/i
    ],
    keywords: ['explore', 'analyze', 'explain', 'code', 'kya', 'samjho']
  },
  {
    intent: 'deploy',
    patterns: [
      /\b(deploy|host|publish|live|launch|deploy|host)\b/i,
      /\b(cloudflare|vercel|netlify|production|live)\b/i
    ],
    keywords: ['deploy', 'host', 'live', 'production']
  },
  {
    intent: 'file_operation',
    patterns: [
      /\b(delete|remove|edit|update|modify|rename|change|add|create)\b/i,
      /\b(file|folder|directory|path)\b/i
    ],
    keywords: ['delete', 'remove', 'edit', 'update', 'file', 'folder']
  }
];

export function detectIntent(message: string): IntentType {
  const lowerMessage = message.toLowerCase();
  
  // Check for project creation (highest priority)
  const createPatterns = INTENT_PATTERNS.find(p => p.intent === 'create_project');
  if (createPatterns) {
    const hasCreateKeyword = createPatterns.keywords.some(k => lowerMessage.includes(k));
    const hasProjectKeyword = /\b(app|website|project|tool|bot|page|component|feature|todo|chat|ecommerce|payment|login|auth)\b/i.test(message);
    
    if (hasCreateKeyword || hasProjectKeyword) {
      return 'create_project';
    }
  }
  
  // Check for bug fixing
  const bugPatterns = INTENT_PATTERNS.find(p => p.intent === 'fix_bug');
  if (bugPatterns) {
    const hasBugKeyword = bugPatterns.keywords.some(k => lowerMessage.includes(k));
    if (hasBugKeyword) {
      return 'fix_bug';
    }
  }
  
  // Check for code exploration
  const explorePatterns = INTENT_PATTERNS.find(p => p.intent === 'explore_code');
  if (explorePatterns) {
    const hasExploreKeyword = explorePatterns.keywords.some(k => lowerMessage.includes(k));
    if (hasExploreKeyword) {
      return 'explore_code';
    }
  }
  
  // Check for deployment
  const deployPatterns = INTENT_PATTERNS.find(p => p.intent === 'deploy');
  if (deployPatterns) {
    const hasDeployKeyword = deployPatterns.keywords.some(k => lowerMessage.includes(k));
    if (hasDeployKeyword) {
      return 'deploy';
    }
  }
  
  // Check for file operations
  const filePatterns = INTENT_PATTERNS.find(p => p.intent === 'file_operation');
  if (filePatterns) {
    const hasFileKeyword = filePatterns.keywords.some(k => lowerMessage.includes(k));
    if (hasFileKeyword) {
      return 'file_operation';
    }
  }
  
  // Default to chat
  return 'chat';
}

export function getAgentTypeForIntent(intent: IntentType): string {
  switch (intent) {
    case 'create_project':
    case 'modify_project':
      return 'planner';
    case 'fix_bug':
      return 'debug';
    case 'explore_code':
      return 'explore';
    case 'deploy':
      return 'build';
    case 'file_operation':
      return 'build';
    default:
      return 'planner';
  }
}
