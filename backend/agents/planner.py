import json
import logging
from .base import call_llm_json

logger = logging.getLogger(__name__)

async def planner_agent(idea: str, research: dict) -> dict:
    logger.info("Starting planner_agent")
    fallback = {
        "architecture": "Unable to generate — please retry.",
        "architecture_mermaid": "graph TD\n  A[Frontend] --> B[Backend]",
        "tech_stack": [],
        "architecture_components": [],
        "roadmap": [],
        "timeline": "Unable to generate — please retry.",
        "documentation": {
            "overview": "Unable to generate — please retry.",
            "sections": []
        }
    }
    try:
        system_prompt = (
            "You are a Senior Principal Software Architect and Technical Planner.\n"
            "Your job is to translate a startup idea and its associated domain research into a comprehensive, "
            "production-grade technical plan. Every output you generate must be unique, highly specific to the "
            "technical domain of the idea, and explicitly grounded in the provided research data (APIs, existing solutions, "
            "academic papers, datasets).\n\n"
            "CRITICAL CONSTRAINTS & REQUIREMENTS:\n"
            "1. NO GENERIC ROADMAPS: Completely avoid generic project phases like 'UI Development', 'Testing', 'Backend setup', "
            "or 'Core Features'. Every milestone and task must represent concrete engineering tasks specific to this system.\n"
            "2. CONCRETE IMPLEMENTATION ACTIONS: Tasks must describe technical actions (e.g., 'Implement spaced repetition scheduling "
            "using the SM-2 algorithm', 'Configure FAISS index with inner-product similarity for vector matching').\n"
            "3. STYLED, LAYERED MERMAID DIAGRAMS:\n"
            "   - Group components using clean Mermaid subgraphs (e.g. Client Layer, Backend Services, AI / ML Layer, Data Layer, External APIs).\n"
            "   - Every diagram must contain between 8 to 14 nodes, representing detailed architecture components.\n"
            "   - Avoid plain arrows. Every edge connector MUST have a clear data flow label (e.g., '-->|raw query|' or '-->|access token|').\n"
            "   - Assign custom color definitions matching the app's clean palette using classDef. Always define classes for 'client', "
            "     'service', 'ai', 'data', and 'ext', and assign them using `:::className` syntax.\n"
            "   - Ensure all subgraphs use double-quoted labels (e.g., `subgraph Client_Layer[\"Client Layer\"]`) to prevent parsing syntax errors.\n"
            "4. SYSTEMATIC GROUNDING: Recommending libraries or databases must include domain-specific technical justifications. "
            "   Cross-reference findings from the research phase (e.g., open source libraries, APIs, datasets) in the plan.\n"
            "5. MANDATORY CITATION: At least 3 of the roadmap tasks across all milestones MUST explicitly reference "
            "a specific named item from the Research JSON below (an exact repo name, paper title, API name, or dataset) — "
            "not a paraphrase, the literal name. If Research contains fewer than 3 usable items, state in that task's "
            "rationale that no verified source exists and flag it as an assumption.\n"
            "6. COMPREHENSIVE 5-8 PHASE ROADMAP: You MUST generate exactly 5 to 8 phases. Each phase milestone name must explicitly list the exact product features being built in that phase (e.g. 'Phase 3: Core Features & Scope (Study Plan, Quizzes, Analytics)'). DO NOT output only 2 or 3 phases. DO NOT output vague milestone names like 'Develop Interface'.\n"
        )

        few_shot_examples = """
### FEW-SHOT EXAMPLE 1 (AI Study Buddy):
Idea: "AI Study Buddy with Spaced Repetition"
Plan JSON:
{
  "architecture": "A multi-layered design separating client interfaces, caching layers, and core algorithms. The system splits concept extraction from the core spaced-repetition logic, utilizing an in-memory Redis session store to ensure minimal DB latency.",
  "tech_stack": [
    "React (Vite) - Highly responsive SPA client for card reviews",
    "FastAPI - Async gateway enabling high concurrency request routing",
    "spaCy - Natural Language Processing library for offline term extraction",
    "PostgreSQL - Relational database for structured Leitner and user scheduling logs",
    "Redis - Cache for active review sessions and session tokens"
  ],
  "architecture_components": [
    {
      "component": "Leitner-based Spaced Repetition Scheduler",
      "technology": "Custom Python Core Engine",
      "rationale": "Required to dynamically calculate personalized card recall intervals using the SM-2 algorithm based on student response values."
    },
    {
      "component": "Concept Extraction Pipeline",
      "technology": "spaCy Core NLP",
      "rationale": "Parses textbooks or notes uploaded by users to extract keywords and definitions without requiring expensive external LLM API queries."
    },
    {
      "component": "Relational Study Store",
      "technology": "PostgreSQL",
      "rationale": "Ensures transactional data safety when updating complex nested study logs and Leitner card intervals."
    }
  ],
  "roadmap": [
    {
      "milestone": "Implement Leitner-Based Flashcard Scheduling Engine",
      "duration": "5 days",
      "tasks": [
        {
          "title": "Define PostgreSQL Scheduling Schemas",
          "description": "Establish tables for cards, user progress tracks, and review histories with indexes on user_id.",
          "rationale": "Essential to record study performance metrics and card retrieval logs safely."
        },
        {
          "title": "Build SM-2 Recall Calculations",
          "description": "Code the algorithm calculating next interval, ease factor, and repetition count from review ratings (0-5).",
          "rationale": "Powers the core customization feature, adapting study loops to student memory decay curves."
        }
      ]
    }
  ],
  "architecture_mermaid": "graph TD\\n  classDef client fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0369a1;\\n  classDef service fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#3730a3;\\n  classDef ai fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#6b21a8;\\n  classDef data fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#065f46;\\n  classDef ext fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#92400e;\\n\\n  subgraph Client_Layer[\\\"Client Layer\\\"]\\n    A[React SPA Client]:::client\\n  end\\n\\n  subgraph Backend_Services[\\\"Backend Services\\\"]\\n    B[FastAPI Router]:::service\\n    C[SM-2 Scheduler Core]:::service\\n  end\\n\\n  subgraph AI_Layer[\\\"AI & ML Core\\\"]\\n    D[spaCy Tag Extractor]:::ai\\n  end\\n\\n  subgraph Data_Layer[\\\"Data Stores\\\"]\\n    E[PostgreSQL Database]:::data\\n    F[Redis Session Cache]:::data\\n  end\\n\\n  A -->|HTTPS Requests| B\\n  B -->|Validate Session| F\\n  B -->|Retrieve Cards| E\\n  B -->|Parse text uploads| D\\n  B -->|Compute intervals| C\\n  C -->|Write new review times| E",
  "timeline": "6 weeks total development time with a 2-engineer engineering team.",
  "documentation": {
    "overview": "Technical execution plan for Study Buddy concept mapping and flashcard scheduler.",
    "sections": [
      {
        "heading": "Database Scaling and Cache Retention",
        "content": "To prevent high database load, card scheduling parameters are buffered in Redis active queues and flushed asynchronously to PostgreSQL every 5 minutes."
      }
    ]
  }
}

### FEW-SHOT EXAMPLE 2 (Smart Hostel Food Waste Tracker):
Idea: "Smart Hostel Food Waste Tracker using computer vision on plate scans"
Plan JSON:
{
  "architecture": "An edge-to-cloud IoT pipeline combining local plate scanning via Raspberry Pi cameras and centralized cloud analytics. Edge devices perform lightweight image capture and preprocessing before streaming to a cloud backend for heavy computer vision inference and real-time dashboard updates.",
  "tech_stack": [
    "Raspberry Pi 4 / Camera Module 3 - Hardware layer for plate capture",
    "OpenCV & Python - Edge image processing and payload formatting",
    "FastAPI & WebSockets - High-throughput ingestion API for edge streams",
    "YOLOv8 - Object detection for food volume and type estimation",
    "PostgreSQL & TimescaleDB - Time-series storage for waste metrics",
    "Next.js & Tailwind - Admin dashboard for hostel management"
  ],
  "architecture_components": [
    {
      "component": "Edge Capture Node",
      "technology": "Python / OpenCV",
      "rationale": "Required to handle hardware triggers, compress images, and maintain robust network connections over spotty hostel Wi-Fi."
    },
    {
      "component": "Inference Engine",
      "technology": "YOLOv8 via PyTorch",
      "rationale": "Provides fast, accurate bounding boxes and area calculations on food scraps, offloading processing from edge devices."
    },
    {
      "component": "Time-Series Store",
      "technology": "TimescaleDB",
      "rationale": "Optimizes aggregation queries (e.g., 'total waste per week') which are critical for hostel food purchasing adjustments."
    }
  ],
  "roadmap": [
    {
      "milestone": "Build Edge Image Ingestion Pipeline",
      "duration": "7 days",
      "tasks": [
        {
          "title": "Configure Raspberry Pi Camera Polling",
          "description": "Set up a Python daemon using OpenCV to capture plate images on a hardware button trigger.",
          "rationale": "Forms the foundational hardware-software bridge for the entire data pipeline."
        },
        {
          "title": "Implement WebSocket Upload Service",
          "description": "Build a FastAPI WebSocket endpoint to receive compressed image payloads from the edge nodes.",
          "rationale": "Ensures low-latency streaming and allows immediate ACK responses back to the hardware."
        }
      ]
    }
  ],
  "architecture_mermaid": "graph TD\\n  classDef client fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0369a1;\\n  classDef service fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#3730a3;\\n  classDef ai fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#6b21a8;\\n  classDef data fill:#d1fae5,stroke:#059669,stroke-width:2px,color:#065f46;\\n  classDef ext fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#92400e;\\n\\n  subgraph Edge_Layer[\\\"IoT Edge\\\"]\\n    A[Raspberry Pi Camera]:::client\\n    B[OpenCV Preprocessor]:::client\\n  end\\n\\n  subgraph Backend_Services[\\\"Cloud Backend\\\"]\\n    C[FastAPI Ingestion]:::service\\n    E[Dashboard API]:::service\\n  end\\n\\n  subgraph AI_Layer[\\\"AI Inference\\\"]\\n    D[YOLOv8 Processor]:::ai\\n  end\\n\\n  subgraph Data_Layer[\\\"Data Stores\\\"]\\n    F[TimescaleDB]:::data\\n  end\\n\\n  A -->|Raw Image| B\\n  B -->|WebSocket Stream| C\\n  C -->|Inference Req| D\\n  D -->|Waste Metrics| F\\n  E -->|Query Aggregates| F",
  "timeline": "8 weeks total development time with 1 hardware/IoT engineer and 1 backend/AI engineer.",
  "documentation": {
    "overview": "Technical execution plan for computer vision plate scanning and food waste analytics.",
    "sections": [
      {
        "heading": "Network Resilience",
        "content": "Edge nodes use a local SQLite buffer to store images if the hostel Wi-Fi drops, syncing to the cloud API once connection is restored."
      }
    ]
  }
}
"""

        user_prompt = f"""
{few_shot_examples}

---

Idea: "{idea}"
Research: {json.dumps(research)}

Generate a detailed, technical plan for the above Idea, heavily utilizing details from the Research data.
Your output MUST be a valid JSON object matching the schema below. Do not wrap in markdown or add text outside the JSON.

JSON Schema:
{{
  "architecture": "string, 3-5 sentences analyzing components, integrations, and performance aspects",
  "architecture_mermaid": "string, a STRICTLY VALID, styled Mermaid.js flowchart. Use layered subgraphs, labeled arrows, classDef styles (client, service, ai, data, ext), and escaped newlines (\\\\n) for formatting.",
  "tech_stack": [
    "string - e.g., 'React (Vite) - chosen for low overhead bundle size and rapid UI rendering'"
  ],
  "architecture_components": [
    {{
      "component": "string - component name",
      "technology": "string - technology used",
      "rationale": "string - idea-specific reason explaining why it is required and how it contributes"
    }}
  ],
  "roadmap": [
    {{
      "milestone": "string - e.g., 'Phase 2: Core Features (Study Plan, Quizzes, Tracking)'. MUST generate exactly 5 to 8 distinct phases, heavily specifying exact application features.",
      "duration": "string - e.g. '2 weeks'",
      "tasks": [
        {{
          "title": "string - concrete task title",
          "description": "string - highly detailed and intellectual technical action plan (3-5 sentences) as if architected by a senior staff engineer",
          "rationale": "string - deep technical rationale and justification (2-4 sentences) explaining why this is the optimal approach"
        }}
      ]
    }}
  ],
  "timeline": "string, one-sentence timeline estimation",
  "documentation": {{
    "overview": "string, 2-3 sentences overview",
    "sections": [
      {{
        "heading": "string",
        "content": "string, 2-4 sentences outlining design rationale"
      }}
    ]
  }}
}}
"""
        result = await call_llm_json(system_prompt, user_prompt, temperature=0.3)
        logger.info("Successfully completed planner_agent")
        return result
    except Exception as e:
        logger.error(f"Failed planner_agent: {e}")
        return fallback
