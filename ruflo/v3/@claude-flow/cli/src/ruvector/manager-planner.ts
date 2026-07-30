/**
 * Ruflo Manager Planner
 *
 * Implements Phase 1 Orchestration Planning for the Ruflo Manager Agent.
 * Decomposes user prompts into Intent, Complexity, Workflow Selection,
 * Specialized Agent Selection, Per-Agent Model Routing, Execution Graph (DAG),
 * and Expected Deliverables.
 */

export interface AgentPlanAssignment {
  agentType: string;
  role: string;
  provider: 'openrouter' | 'gemini' | 'anthropic' | 'ollama';
  model: string;
  tier: 1 | 2 | 3;
  dependencies: string[];
}

export interface ExecutionGraphStage {
  stageId: string;
  name: string;
  parallelAgents: string[];
  dependsOnStageId?: string;
}

export interface OrchestrationPlan {
  prompt: string;
  intent: string;
  complexity: 'Low' | 'Medium' | 'High' | 'Critical';
  selectedWorkflow: string;
  requiredAgents: AgentPlanAssignment[];
  executionGraph: ExecutionGraphStage[];
  expectedOutputs: string[];
}

export class ManagerPlanner {
  /**
   * Analyze prompt and generate complete multi-agent orchestration plan.
   */
  public static plan(prompt: string): OrchestrationPlan {
    const lower = prompt.toLowerCase();

    // 1. Intent Detection
    let intent = 'General Task Execution';
    if (lower.includes('fastapi') || lower.includes('api') || lower.includes('backend') || lower.includes('express') || lower.includes('django')) {
      intent = 'Backend API Development';
    } else if (lower.includes('react') || lower.includes('frontend') || lower.includes('ui') || lower.includes('component')) {
      intent = 'Frontend Application Development';
    } else if (lower.includes('security') || lower.includes('audit') || lower.includes('cve') || lower.includes('vulnerability')) {
      intent = 'Security Audit & Vulnerability Remediation';
    } else if (lower.includes('refactor') || lower.includes('clean') || lower.includes('optimize')) {
      intent = 'Codebase Refactoring & Optimization';
    } else if (lower.includes('test') || lower.includes('coverage') || lower.includes('tdd')) {
      intent = 'Test Architecture & Quality Assurance';
    }

    // 2. Complexity Analysis
    let complexity: OrchestrationPlan['complexity'] = 'Medium';
    const wordCount = prompt.split(/\s+/).length;
    const hasProduction = lower.includes('production') || lower.includes('jwt') || lower.includes('docker') || lower.includes('microservice');
    if (hasProduction || wordCount > 25) {
      complexity = 'High';
    } else if (wordCount < 6) {
      complexity = 'Low';
    }

    // 3. Workflow Selection
    let selectedWorkflow = 'Development';
    if (intent.includes('Security')) selectedWorkflow = 'security-audit';
    else if (intent.includes('Refactoring')) selectedWorkflow = 'refactoring';
    else if (intent.includes('Test')) selectedWorkflow = 'testing';
    else if (complexity === 'High') selectedWorkflow = 'sparc';

    // 4. Specialized Agents & Model Allocations
    const requiredAgents: AgentPlanAssignment[] = [];
    const expectedOutputs: string[] = [];

    if (intent === 'Backend API Development') {
      requiredAgents.push(
        {
          agentType: 'architect',
          role: 'System & API Schema Architecture',
          provider: 'openrouter',
          model: 'deepseek/deepseek-r1',
          tier: 3,
          dependencies: []
        },
        {
          agentType: 'coder',
          role: 'FastAPI Routes & JWT Authentication Implementation',
          provider: 'openrouter',
          model: 'deepseek/deepseek-chat',
          tier: 2,
          dependencies: ['architect']
        },
        {
          agentType: 'reviewer',
          role: 'Code Quality & Security Verification',
          provider: 'openrouter',
          model: 'qwen/qwen-2.5-coder-32b-instruct',
          tier: 2,
          dependencies: ['coder']
        },
        {
          agentType: 'tester',
          role: 'Pytest Suite & Docker Containerization Test',
          provider: 'gemini',
          model: 'gemini-2.0-flash',
          tier: 1,
          dependencies: ['reviewer']
        }
      );

      expectedOutputs.push(
        'FastAPI Application Structure (`main.py`, `routers/`, `schemas/`)',
        'JWT Auth Middleware & Security Module',
        'Dockerfile & docker-compose.yml setup',
        'Pytest Unit & Integration Test Suite',
        'Comprehensive README.md with Setup Instructions'
      );
    } else if (intent.includes('Security')) {
      requiredAgents.push(
        {
          agentType: 'security-architect',
          role: 'Threat Modeling & Risk Assessment',
          provider: 'openrouter',
          model: 'deepseek/deepseek-r1',
          tier: 3,
          dependencies: []
        },
        {
          agentType: 'reviewer',
          role: 'Static Code Analysis & CVE Audit',
          provider: 'openrouter',
          model: 'qwen/qwen-2.5-coder-32b-instruct',
          tier: 2,
          dependencies: ['security-architect']
        }
      );
      expectedOutputs.push('Security Vulnerability Report', 'Remediation Pull Request');
    } else {
      // Default fallback plan
      requiredAgents.push(
        {
          agentType: 'architect',
          role: 'Task Analysis & Design',
          provider: 'openrouter',
          model: 'deepseek/deepseek-r1',
          tier: 3,
          dependencies: []
        },
        {
          agentType: 'coder',
          role: 'Task Execution & Implementation',
          provider: 'openrouter',
          model: 'deepseek/deepseek-chat',
          tier: 2,
          dependencies: ['architect']
        },
        {
          agentType: 'tester',
          role: 'Verification & Output Validation',
          provider: 'gemini',
          model: 'gemini-2.0-flash',
          tier: 1,
          dependencies: ['coder']
        }
      );
      expectedOutputs.push('Implementation Source Code', 'Verification Report');
    }

    // 5. Execution Graph (DAG Construction)
    const executionGraph: ExecutionGraphStage[] = [
      { stageId: 'stage-1', name: 'Architectural Design', parallelAgents: ['architect', 'security-architect'].filter(a => requiredAgents.some(r => r.agentType === a)) },
      { stageId: 'stage-2', name: 'Implementation & Coding', parallelAgents: ['coder'].filter(a => requiredAgents.some(r => r.agentType === a)), dependsOnStageId: 'stage-1' },
      { stageId: 'stage-3', name: 'Code Review & Security Audit', parallelAgents: ['reviewer'].filter(a => requiredAgents.some(r => r.agentType === a)), dependsOnStageId: 'stage-2' },
      { stageId: 'stage-4', name: 'Automated Testing & Containerization', parallelAgents: ['tester'].filter(a => requiredAgents.some(r => r.agentType === a)), dependsOnStageId: 'stage-3' }
    ].filter(s => s.parallelAgents.length > 0);

    return {
      prompt,
      intent,
      complexity,
      selectedWorkflow,
      requiredAgents,
      executionGraph,
      expectedOutputs
    };
  }
}
