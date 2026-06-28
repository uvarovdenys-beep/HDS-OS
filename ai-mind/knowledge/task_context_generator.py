#!/usr/bin/env python3
"""
HDS6 Task Context Generator
Генерує локалізовані контексти для ШІ на основі типу таски та вимог

Authors: Уваров Денис Юрійович, Александров Микита Олександрович, Уварова Анастасія Сергіївна
License: HDS6 Standard
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


@dataclass
class TaskContext:
    """Контекст таски для ШІ."""
    task_id: str
    task_type: str
    description: str
    capabilities: List[str]
    constraints: List[str]
    forbidden: List[str]
    required: List[str]
    full_docs_path: str
    extended_info: Optional[Dict[str, Any]] = None


class TaskContextGenerator:
    """Генератор контекстів тасок для ШІ асистентів."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.templates_file = base_dir / "ai-mind" / "knowledge" / "task_context_templates.json"
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Any]:
        """Завантажити шаблони контекстів."""
        if self.templates_file.exists():
            with open(self.templates_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # Створити базові шаблони якщо файл не існує
        return self._create_default_templates()
    
    def _create_default_templates(self) -> Dict[str, Any]:
        """Створити шаблони за замовчуванням."""
        templates = {
            "web_research": {
                "capabilities": [
                    "Browser agent with headless mode",
                    "Content extraction and analysis", 
                    "Screenshot capture",
                    "Text summarization"
                ],
                "constraints": [
                    "Security level: STANDARD",
                    "Max requests: 10 per minute",
                    "Content filtering: ENABLED"
                ],
                "forbidden": [
                    "Direct file downloads",
                    "Form submissions", 
                    "JavaScript execution",
                    "Access to sensitive domains"
                ],
                "required": [
                    "Use HDS6Scribe for all file operations",
                    "Include task_id in all operations",
                    "Validate content before processing"
                ]
            },
            "script_execution": {
                "capabilities": [
                    "AI-DRIVER pipeline execution",
                    "Script validation and security check",
                    "Resource monitoring",
                    "Progress tracking"
                ],
                "constraints": [
                    "Max execution time: 5 minutes",
                    "Memory limit: 512MB",
                    "R-01 compliance: ENFORCED"
                ],
                "forbidden": [
                    "Direct file writes (use HDS6Scribe)",
                    "Network requests without approval",
                    "System-level operations",
                    "Infinite loops"
                ],
                "required": [
                    "Include task_id in script",
                    "Handle all exceptions",
                    "Log execution progress",
                    "Cleanup resources on completion"
                ]
            },
            "vision_automation": {
                "capabilities": [
                    "Screen capture and analysis",
                    "Element detection and interaction",
                    "Mouse/keyboard automation",
                    "Safe mode protection"
                ],
                "constraints": [
                    "Safe mode: ALWAYS ENABLED",
                    "Max actions per minute: 30",
                    "Confidence threshold: 0.8"
                ],
                "forbidden": [
                    "System-level interactions",
                    "Administrative operations",
                    "Password input automation",
                    "File system access"
                ],
                "required": [
                    "Verify element before interaction",
                    "Use human-like timing",
                    "Log all actions",
                    "Emergency stop capability"
                ]
            },
            "data_analysis": {
                "capabilities": [
                    "Data processing and transformation",
                    "Statistical analysis",
                    "Chart generation",
                    "Report creation"
                ],
                "constraints": [
                    "Max file size: 100MB",
                    "Processing time limit: 10 minutes",
                    "Memory usage: 1GB max"
                ],
                "forbidden": [
                    "External data sources",
                    "Network connections",
                    "System modifications",
                    "Sensitive data exposure"
                ],
                "required": [
                    "Validate input data format",
                    "Use HDS6Scribe for outputs",
                    "Include data provenance",
                    "Handle missing values appropriately"
                ]
            },
            "integration": {
                "capabilities": [
                    "Component orchestration",
                    "Task dependency management",
                    "Resource allocation",
                    "Progress monitoring"
                ],
                "constraints": [
                    "Max concurrent components: 3",
                    "Total execution time: 15 minutes",
                    "Resource monitoring: ENABLED"
                ],
                "forbidden": [
                    "Circular dependencies",
                    "Resource exhaustion",
                    "Unbounded loops",
                    "Direct component bypass"
                ],
                "required": [
                    "Define clear dependencies",
                    "Monitor resource usage",
                    "Handle component failures",
                    "Provide progress updates"
                ]
            }
        }
        
        # Зберегти шаблони
        self.templates_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            json.dump(templates, f, indent=2, ensure_ascii=False)
        
        return templates
    
    def generate_context(self, task_id: str, task_type: str, description: str, 
                        extended: bool = False) -> TaskContext:
        """Згенерувати контекст для таски."""
        
        if task_type not in self.templates:
            raise ValueError(f"Unknown task type: {task_type}")
        
        template = self.templates[task_type]
        
        context = TaskContext(
            task_id=task_id,
            task_type=task_type,
            description=description,
            capabilities=template["capabilities"],
            constraints=template["constraints"],
            forbidden=template["forbidden"],
            required=template["required"],
            full_docs_path="ai-mind/knowledge/hds6_ai_complete_documentation.md"
        )
        
        if extended:
            context.extended_info = self._generate_extended_info(task_type)
        
        return context
    
    def _generate_extended_info(self, task_type: str) -> Dict[str, Any]:
        """Згенерувати розширену інформацію."""
        extended_info = {
            "examples": [],
            "troubleshooting": [],
            "references": []
        }
        
        if task_type == "web_research":
            extended_info["examples"] = [
                "Extract article content from Wikipedia",
                "Analyze product information from e-commerce site",
                "Research technical documentation"
            ]
            extended_info["troubleshooting"] = [
                "If navigation fails, check domain whitelist",
                "For slow loading pages, increase timeout",
                "Content extraction issues: verify page structure"
            ]
        
        elif task_type == "script_execution":
            extended_info["examples"] = [
                "Process CSV data and generate report",
                "Automated data validation and cleaning",
                "Batch file processing with error handling"
            ]
            extended_info["troubleshooting"] = [
                "Memory issues: reduce data chunk size",
                "Timeout errors: optimize algorithm efficiency",
                "Import errors: verify library availability"
            ]
        
        elif task_type == "vision_automation":
            extended_info["examples"] = [
                "Automated GUI testing workflow",
                "Form filling with validation",
                "Screenshot-based monitoring"
            ]
            extended_info["troubleshooting"] = [
                "Element not found: check selectors and timing",
                "Click failures: verify element visibility",
                "Safe mode violations: review action permissions"
            ]
        
        return extended_info
    
    def format_context(self, context: TaskContext, format_type: str = "minimal") -> str:
        """Форматувати контекст для ШІ."""
        
        if format_type == "minimal":
            return self._format_minimal(context)
        elif format_type == "standard":
            return self._format_standard(context)
        elif format_type == "full":
            return self._format_full(context)
        else:
            raise ValueError(f"Unknown format type: {format_type}")
    
    def _format_minimal(self, context: TaskContext) -> str:
        """Мінімальний формат - тільки критична інформація."""
        lines = [
            f"TASK: {context.task_id} - {context.description}",
            f"CAPABILITIES: {', '.join(context.capabilities[:3])}...",
            f"CONSTRAINTS: {', '.join(context.constraints[:2])}",
            f"FORBIDDEN: {', '.join(context.forbidden[:2])}",
            f"REQUIRED: {', '.join(context.required[:2])}",
            f"FULL_DOCS: {context.full_docs_path}"
        ]
        return "\n".join(lines)
    
    def _format_standard(self, context: TaskContext) -> str:
        """Стандартний формат - повна критична інформація."""
        lines = [
            f"TASK: {context.task_id} - {context.description}",
            f"CONTEXT: {context.task_type.upper()} task execution",
            "",
            "CAPABILITIES:",
            *[f"- {cap}" for cap in context.capabilities],
            "",
            "CONSTRAINTS:",
            *[f"- {con}" for con in context.constraints],
            "",
            "FORBIDDEN:",
            *[f"- {forb}" for forb in context.forbidden],
            "",
            "REQUIRED:",
            *[f"- {req}" for req in context.required],
            "",
            f"FULL_DOCS: {context.full_docs_path}"
        ]
        
        if context.extended_info:
            lines.extend([
                "",
                "EXTENDED_INFO:",
                f"Examples: {len(context.extended_info.get('examples', []))} available",
                f"Troubleshooting: {len(context.extended_info.get('troubleshooting', []))} items"
            ])
        
        return "\n".join(lines)
    
    def _format_full(self, context: TaskContext) -> str:
        """Повний формат - вся доступна інформація."""
        lines = [
            f"TASK: {context.task_id} - {context.description}",
            f"CONTEXT: {context.task_type.upper()} task execution",
            f"GENERATED: {datetime.now().isoformat()}",
            "",
            "CAPABILITIES:",
            *[f"- {cap}" for cap in context.capabilities],
            "",
            "CONSTRAINTS:",
            *[f"- {con}" for con in context.constraints],
            "",
            "FORBIDDEN:",
            *[f"- {forb}" for forb in context.forbidden],
            "",
            "REQUIRED:",
            *[f"- {req}" for req in context.required],
            "",
            f"FULL_DOCS: {context.full_docs_path}"
        ]
        
        if context.extended_info:
            lines.extend([
                "",
                "EXTENDED INFORMATION:",
                "",
                "EXAMPLES:",
                *[f"• {ex}" for ex in context.extended_info.get('examples', [])],
                "",
                "TROUBLESHOOTING:",
                *[f"• {tr}" for tr in context.extended_info.get('troubleshooting', [])],
                "",
                "REFERENCES:",
                *[f"• {ref}" for ref in context.extended_info.get('references', [])]
            ])
        
        return "\n".join(lines)
    
    def save_context(self, context: TaskContext, filename: str = None):
        """Зберегти контекст у файл."""
        if filename is None:
            filename = f"task_context_{context.task_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        context_file = self.base_dir / "ai-mind" / "cache" / filename
        context_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(context_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(context), f, indent=2, ensure_ascii=False)
        
        return context_file
    
    def get_available_task_types(self) -> List[str]:
        """Отримати список доступних типів тасок."""
        return list(self.templates.keys())


def main():
    """Демонстрація роботи генератора контекстів."""
    base_dir = Path(__file__).parent.parent.parent
    generator = TaskContextGenerator(base_dir)
    
    print("HDS6 Task Context Generator")
    print("=" * 40)
    
    # Приклад генерації контексту
    context = generator.generate_context(
        task_id="WEB_RESEARCH_001",
        task_type="web_research",
        description="Analyze website content for research",
        extended=True
    )
    
    print("\nMINIMAL FORMAT:")
    print("-" * 20)
    print(generator.format_context(context, "minimal"))
    
    print("\nSTANDARD FORMAT:")
    print("-" * 20)
    print(generator.format_context(context, "standard"))
    
    # Зберегти контекст
    saved_file = generator.save_context(context)
    print(f"\nContext saved to: {saved_file}")
    
    print(f"\nAvailable task types: {generator.get_available_task_types()}")


if __name__ == "__main__":
    main()
