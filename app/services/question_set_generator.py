"""
Question Set Generator Service

Generates a complete question set for repository code understanding.
Uses enhanced repository analysis with symbol extraction and relationship graph.
"""

import json
import re
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.llm_client import get_llm_provider
from app.prompts import get_prompt_manager
from app.services.repository_analyzer import repository_analyzer
from app.services.repository_analyzer_enhanced import enhanced_repository_analyzer


class QuestionSetGenerator:
    """Generates a complete question set for repository code understanding."""

    # Phase definitions with quotas
    PHASE_DEFINITIONS = {
        "Panorama Mapping": {
            "description": "Quickly establish what the project is",
            "min_questions": 2,
            "max_questions": 3,
        },
        "Architecture Understanding": {
            "description": "Understand how the project is organized",
            "min_questions": 2,
            "max_questions": 4,
        },
        "Code Detail Completion": {
            "description": "Understand how the current implementation works",
            "min_ratio": 0.85,  # 85% of total questions
        },
        "Use Cases & Scenarios": {
            "description": "Connect code understanding to real usage",
            "min_questions": 1,
            "max_questions": 2,
        },
    }

    def __init__(self):
        self.prompt_manager = get_prompt_manager()
        self.llm_provider = get_llm_provider()

    def generate_question_set(
        self,
        repository_url: str,
        repository_source: str = "remote",
        total_questions: int = 40,
        code_detail_ratio: float = 0.85,
        min_core_file_coverage: float = 0.90,
        ref: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a complete question set for a repository.
        
        Args:
            repository_url: URL or local path of the repository
            repository_source: Source type - 'remote' for URL, 'local' for local path
            total_questions: Total number of questions to generate
            code_detail_ratio: Minimum ratio of code detail questions
            min_core_file_coverage: Minimum core file coverage ratio
            ref: Optional git ref (branch, tag, commit)
            
        Returns:
            Dictionary containing generated questions and metadata
        """
        # Step 1: Analyze repository using enhanced analyzer for local paths
        if repository_source == "local":
            repo_path = Path(repository_url)
            if repo_path.exists() and repo_path.is_dir():
                # Use enhanced analyzer for local repositories
                analysis = enhanced_repository_analyzer.analyze_repository(repo_path)
                # Merge with basic analysis for compatibility
                basic_analysis = repository_analyzer.analyze_repository(repository_url, ref, repository_source)
                analysis.update({
                    "repository_url": repository_url,
                    "ref": ref,
                    "local_path": str(repo_path),
                })
            else:
                analysis = repository_analyzer.analyze_repository(repository_url, ref, repository_source)
        else:
            analysis = repository_analyzer.analyze_repository(repository_url, ref, repository_source)
        
        # Step 2: Plan question distribution
        question_plan = self._plan_question_distribution(
            total_questions, code_detail_ratio, analysis
        )
        
        # Step 3: Generate questions for each phase
        questions = []
        for phase, phase_config in question_plan.items():
            phase_questions = self._generate_phase_questions(
                phase, phase_config, analysis, previous_questions=questions
            )
            questions.extend(phase_questions)
        
        # Step 4: Validate and repair (auto-generate more if needed)
        questions, validation_result = self._validate_and_repair(
            questions, analysis, total_questions, code_detail_ratio, min_core_file_coverage
        )
        
        # Step 5: Improve coherence between questions
        questions = self._improve_coherence(questions)
        
        # Step 6: Generate coverage report
        coverage_report = self._generate_coverage_report(
            questions, analysis, min_core_file_coverage
        )
        
        return {
            "questions": questions,
            "validation_report": validation_result,
            "coverage_report": coverage_report,
            "repository_analysis": analysis,
        }

    def _plan_question_distribution(
        self,
        total_questions: int,
        code_detail_ratio: float,
        analysis: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        """Plan how questions should be distributed across phases."""
        plan = {}
        
        # Calculate code detail questions
        code_detail_count = int(total_questions * code_detail_ratio)
        remaining = total_questions - code_detail_count
        
        # Distribute remaining questions to other phases
        panorama_count = min(2, remaining // 3)
        architecture_count = min(3, remaining // 3)
        use_cases_count = remaining - panorama_count - architecture_count
        
        # Ensure minimums
        panorama_count = max(2, panorama_count)
        architecture_count = max(2, architecture_count)
        use_cases_count = max(1, use_cases_count)
        
        # Adjust if needed
        total_allocated = panorama_count + architecture_count + code_detail_count + use_cases_count
        if total_allocated > total_questions:
            # Reduce use_cases first
            use_cases_count = max(1, use_cases_count - (total_allocated - total_questions))
        
        plan["Panorama Mapping"] = {
            "count": panorama_count,
            "description": self.PHASE_DEFINITIONS["Panorama Mapping"]["description"],
        }
        
        plan["Architecture Understanding"] = {
            "count": architecture_count,
            "description": self.PHASE_DEFINITIONS["Architecture Understanding"]["description"],
        }
        
        plan["Code Detail Completion"] = {
            "count": code_detail_count,
            "description": self.PHASE_DEFINITIONS["Code Detail Completion"]["description"],
            "core_files": analysis.get("core_files", []),
        }
        
        plan["Use Cases & Scenarios"] = {
            "count": use_cases_count,
            "description": self.PHASE_DEFINITIONS["Use Cases & Scenarios"]["description"],
        }
        
        return plan

    def _generate_phase_questions(
        self,
        phase: str,
        phase_config: dict[str, Any],
        analysis: dict[str, Any],
        previous_questions: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate questions for a specific phase."""
        if phase == "Code Detail Completion":
            return self._generate_code_detail_questions(phase_config, analysis)
        else:
            return self._generate_generic_phase_questions(phase, phase_config, analysis, previous_questions)

    # Question angles for generating multiple questions per file
    QUESTION_ANGLES = [
        {"name": "implementation", "focus": "How does {symbol} work internally? What algorithms or data structures does it use?"},
        {"name": "data_flow", "focus": "What data does {symbol} receive, transform, and return? How does data flow through it?"},
        {"name": "error_handling", "focus": "How does {symbol} handle errors, edge cases, or invalid inputs?"},
        {"name": "state_management", "focus": "What state does {symbol} maintain? How does it manage state transitions?"},
        {"name": "dependencies", "focus": "How does {symbol} interact with its dependencies? What contracts does it rely on?"},
        {"name": "side_effects", "focus": "What side effects does {symbol} produce? Does it modify external state, files, or databases?"},
        {"name": "performance", "focus": "What are the performance characteristics of {symbol}? Are there any bottlenecks or optimizations?"},
        {"name": "concurrency", "focus": "How does {symbol} handle concurrent access or asynchronous operations?"},
    ]

    def _generate_code_detail_questions(
        self,
        phase_config: dict[str, Any],
        analysis: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Generate code detail questions targeting core files.
        
        Aggressively generates questions to meet target count.
        Uses multiple angles per file and cycles through all core files.
        """
        questions = []
        core_files = phase_config.get("core_files", [])
        target_count = phase_config.get("count", 34)
        
        if not core_files:
            return questions
        
        # Group files by importance
        high_importance = [f for f in core_files if f.get("importance", 0) > 0.7]
        medium_importance = [f for f in core_files if 0.5 < f.get("importance", 0) <= 0.7]
        low_importance = [f for f in core_files if f.get("importance", 0) <= 0.5]
        
        # Ensure we have at least some files in each category
        if not high_importance and core_files:
            high_importance = core_files[:max(1, len(core_files) // 3)]
        if not medium_importance and len(core_files) > 1:
            medium_importance = core_files[max(1, len(core_files) // 3):max(2, 2 * len(core_files) // 3)]
        
        # Calculate questions per file to meet target
        total_files = len(core_files)
        questions_per_file = max(len(self.QUESTION_ANGLES), (target_count // total_files) + 1)
        
        # Phase 1: Generate questions for all files with multiple angles
        all_files_ordered = high_importance + medium_importance + low_importance
        
        for file_info in all_files_ordered:
            if len(questions) >= target_count:
                break
            
            # Calculate how many questions this file should get based on importance
            importance = file_info.get("importance", 0)
            if importance > 0.7:
                max_angles = min(len(self.QUESTION_ANGLES), questions_per_file)
            elif importance > 0.5:
                max_angles = min(5, questions_per_file // 2)
            else:
                max_angles = min(3, questions_per_file // 3)
            
            # Generate questions with different angles
            file_questions = self._generate_multi_angle_questions(
                file_info, analysis, "high" if importance > 0.7 else ("medium" if importance > 0.5 else "low"),
                max_angles
            )
            questions.extend(file_questions)
        
        # Phase 2: If still need more, cycle through files again with new angles
        if len(questions) < target_count:
            remaining = target_count - len(questions)
            for file_info in all_files_ordered:
                if remaining <= 0:
                    break
                
                # Get angles already used for this file
                used_angles = [q.get("angle") for q in questions 
                              if q.get("target_files", [None])[0] == file_info.get("path")]
                
                # Generate with unused angles
                extra_questions = self._generate_multi_angle_questions(
                    file_info, analysis, "high", min(4, remaining),
                    skip_angles=used_angles
                )
                questions.extend(extra_questions)
                remaining -= len(extra_questions)
        
        # Phase 3: If STILL need more, generate with all angles including duplicates
        if len(questions) < target_count:
            remaining = target_count - len(questions)
            for file_info in high_importance + medium_importance:
                if remaining <= 0:
                    break
                
                # Generate without angle restriction
                for angle in self.QUESTION_ANGLES:
                    if remaining <= 0:
                        break
                    question = self._generate_file_specific_question(
                        file_info, analysis, "high", angle=angle
                    )
                    if question:
                        questions.append(question)
                        remaining -= 1
        
        # Remove duplicate questions
        questions = self._deduplicate_questions(questions)
        
        return questions[:target_count]

    def _generate_multi_angle_questions(
        self,
        file_info: dict[str, Any],
        analysis: dict[str, Any],
        importance_level: str,
        count: int,
        skip_angles: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate multiple questions for a file from different angles."""
        questions = []
        skip_angles = skip_angles or []
        
        # Select angles to use (skip already used ones)
        available_angles = [a for a in self.QUESTION_ANGLES if a["name"] not in skip_angles]
        
        # Shuffle angles for variety (using deterministic seed based on file path)
        import hashlib
        seed = int(hashlib.md5(file_info.get("path", "").encode()).hexdigest()[:8], 16)
        rng = __import__('random').Random(seed)
        rng.shuffle(available_angles)
        
        for angle in available_angles[:count]:
            question = self._generate_file_specific_question(
                file_info, analysis, importance_level, angle=angle
            )
            if question:
                questions.append(question)
        
        return questions

    def _deduplicate_questions(self, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove duplicate or near-duplicate questions."""
        if not questions:
            return questions
        
        unique_questions = []
        seen_normalized = []
        
        for q in questions:
            text = q.get("question_text", "").lower()
            # Normalize for comparison
            normalized = re.sub(r'[^\w\s]', '', text)
            normalized = ' '.join(normalized.split())
            
            # Check if too similar to existing question
            is_duplicate = False
            for seen in seen_normalized:
                similarity = self._calculate_similarity(normalized, seen)
                if similarity > 0.7:  # Lower threshold for dedup
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_questions.append(q)
                seen_normalized.append(normalized)
        
        return unique_questions

    def _generate_file_specific_question(
        self,
        file_info: dict[str, Any],
        analysis: dict[str, Any],
        importance_level: str,
        angle: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Generate a specific question for a file."""
        file_path = file_info.get("path", "")
        language = file_info.get("language", "")
        
        # Find classes and functions in this file
        # Support both old format (core_classes) and new format (symbols.classes)
        classes = [c for c in analysis.get("core_classes", []) if c.get("file") == file_path]
        functions = [f for f in analysis.get("core_functions", []) if f.get("file") == file_path]
        
        # Enhanced: also check symbols from enhanced analyzer
        symbols = analysis.get("symbols", {})
        if symbols:
            classes.extend([c for c in symbols.get("classes", []) if c.get("file") == file_path])
            functions.extend([f for f in symbols.get("functions", []) if f.get("file") == file_path])
            functions.extend([m for m in symbols.get("methods", []) if m.get("file") == file_path])
        
        # Remove duplicates
        seen_classes = set()
        unique_classes = []
        for c in classes:
            name = c.get("name")
            if name not in seen_classes:
                seen_classes.add(name)
                unique_classes.append(c)
        classes = unique_classes
        
        seen_functions = set()
        unique_functions = []
        for f in functions:
            name = f.get("name")
            if name not in seen_functions:
                seen_functions.add(name)
                unique_functions.append(f)
        functions = unique_functions
        
        # Get relationships for this file
        relationships = analysis.get("relationships", {})
        incoming_deps = []
        outgoing_deps = []
        
        # Find files that import this file
        for imp in relationships.get("imports", []):
            if imp.get("module") and file_path.endswith(imp["module"].replace(".", "/") + ".py"):
                incoming_deps.append(imp["file"])
        
        # Find files this file imports
        for imp in relationships.get("imports", []):
            if imp.get("file") == file_path and imp.get("module"):
                outgoing_deps.append(imp["module"])
        
        # Get routes if any
        routes = [r for r in relationships.get("routes", []) if r.get("file") == file_path]
        
        # Build context for LLM
        context = {
            "file_path": file_path,
            "language": language,
            "importance_level": importance_level,
            "classes": [c.get("name") for c in classes[:5]],  # Limit to 5
            "functions": [f.get("name") for f in functions[:10]],  # Limit to 10
            "frameworks": analysis.get("frameworks", []),
            "incoming_dependencies": incoming_deps[:5],
            "outgoing_dependencies": outgoing_deps[:5],
            "routes": [f"{r.get('method', 'GET')} {r.get('path', '')}" for r in routes[:3]],
            "architectural_patterns": analysis.get("architectural_patterns", []),
            "angle": angle,
        }
        
        # Generate question using LLM
        try:
            # Build angle-specific context
            angle_hint = ""
            if angle:
                # Get the primary symbol for this file
                primary_symbol = context["classes"][0] if context["classes"] else (
                    context["functions"][0] if context["functions"] else file_path
                )
                angle_hint = angle["focus"].format(symbol=primary_symbol)
            
            prompt = self.prompt_manager.render(
                "generate_code_detail_question",
                {
                    "file_path": file_path,
                    "language": language,
                    "classes": ", ".join(context["classes"]) if context["classes"] else "none",
                    "functions": ", ".join(context["functions"]) if context["functions"] else "none",
                    "frameworks": ", ".join(context["frameworks"]) if context["frameworks"] else "none",
                    "importance_level": importance_level,
                    "incoming_dependencies": ", ".join(context["incoming_dependencies"]) if context["incoming_dependencies"] else "none",
                    "outgoing_dependencies": ", ".join(context["outgoing_dependencies"]) if context["outgoing_dependencies"] else "none",
                    "routes": ", ".join(context["routes"]) if context["routes"] else "none",
                    "architectural_patterns": ", ".join(context["architectural_patterns"]) if context["architectural_patterns"] else "none",
                    "angle_hint": angle_hint if angle_hint else "Focus on understanding the core implementation details.",
                }
            )
            
            # Use higher temperature for more natural, varied questions
            temperature = 0.7 if angle else 0.5
            
            response = self.llm_provider.generate_text(
                messages=prompt.messages,
                model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
                temperature=temperature,
            )
            
            # Parse response
            question_text = self._extract_question_from_response(response.text)
            
            # Ensure exactly one question
            question_text = self._ensure_single_question(question_text)
            
            return {
                "phase": "Code Detail Completion",
                "question_text": question_text,
                "target_files": [file_path],
                "target_symbols": context["classes"] + context["functions"],
                "importance_level": importance_level,
                "angle": angle["name"] if angle else "general",
            }
            
        except Exception as e:
            # Fallback to template-based question
            return self._generate_template_question(file_info, context)

    def _generate_template_question(
        self,
        file_info: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate a template-based question as fallback."""
        file_path = context["file_path"]
        classes = context["classes"]
        functions = context["functions"]
        
        if classes:
            question_text = f"How does the `{classes[0]}` class in `{file_path}` work?"
        elif functions:
            question_text = f"What does the `{functions[0]}` function in `{file_path}` do?"
        else:
            question_text = f"What is the purpose of `{file_path}` and how does it work?"
        
        return {
            "phase": "Code Detail Completion",
            "question_text": question_text,
            "target_files": [file_path],
            "target_symbols": classes + functions,
            "importance_level": context["importance_level"],
        }

    def _generate_generic_phase_questions(
        self,
        phase: str,
        phase_config: dict[str, Any],
        analysis: dict[str, Any],
        previous_questions: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate questions for non-code-detail phases."""
        questions = []
        target_count = phase_config.get("count", 2)
        
        # Build context for LLM
        context = {
            "phase": phase,
            "description": phase_config.get("description", ""),
            "repository_url": analysis.get("repository_url", ""),
            "languages": list(analysis.get("languages", {}).keys()),
            "frameworks": analysis.get("frameworks", []),
            "top_level_structure": [s.get("name") for s in analysis.get("top_level_structure", [])],
            "entrypoints": [e.get("file") for e in analysis.get("entrypoints", [])],
        }
        
        # Add enhanced analysis data for Architecture Understanding phase
        if phase == "Architecture Understanding":
            # Architectural patterns
            arch_patterns = analysis.get("architectural_patterns", [])
            context["architectural_patterns"] = ", ".join(arch_patterns) if arch_patterns else "none detected"
            
            # Entry point flow
            entry_flow = analysis.get("entry_point_flow", [])
            if entry_flow:
                flow_descriptions = []
                for flow in entry_flow[:3]:  # Limit to 3 entry points
                    ep = flow.get("entrypoint", "unknown")
                    deps = flow.get("dependencies", [])
                    if deps:
                        flow_descriptions.append(f"{ep} -> [{', '.join(deps[:5])}]")
                    else:
                        flow_descriptions.append(ep)
                context["entry_point_flow"] = "; ".join(flow_descriptions)
            else:
                context["entry_point_flow"] = "none available"
            
            # Dependency summary
            dep_summary = analysis.get("dependency_graph", {})
            highly_depended = dep_summary.get("highly_depended_upon", [])
            if highly_depended:
                dep_list = [f"{d['file']} ({d['count']} refs)" for d in highly_depended[:5]]
                context["dependency_summary"] = ", ".join(dep_list)
            else:
                context["dependency_summary"] = "none available"
        else:
            # For non-architecture phases, provide defaults
            context["architectural_patterns"] = "none"
            context["entry_point_flow"] = "none"
            context["dependency_summary"] = "none"
        
        # Add previous questions for context and coherence
        if previous_questions:
            # Extract question texts from previous questions for context
            previous_question_texts = [q.get("question_text", "") for q in previous_questions[-5:]]  # Last 5 questions
            context["previous_questions"] = previous_question_texts
        else:
            context["previous_questions"] = []
        
        try:
            prompt = self.prompt_manager.render(
                f"generate_{phase.lower().replace(' ', '_')}_questions",
                context
            )
            
            response = self.llm_provider.generate_text(
                messages=prompt.messages,
                model=settings.openai_model if settings.llm_provider == "openai_compatible" else None,
                temperature=0.3,
            )
            
            # Parse multiple questions from response
            parsed_questions = self._parse_multiple_questions(response.text, phase)
            
            # Ensure each question is a single question sentence
            for q in parsed_questions:
                q["question_text"] = self._ensure_single_question(q["question_text"])
            
            questions.extend(parsed_questions[:target_count])
            
        except Exception as e:
            # Fallback to template-based questions
            questions.extend(self._generate_template_phase_questions(phase, context, target_count))
        
        return questions

    def _generate_template_phase_questions(
        self,
        phase: str,
        context: dict[str, Any],
        count: int,
    ) -> list[dict[str, Any]]:
        """Generate template-based questions for a phase."""
        questions = []
        
        if phase == "Panorama Mapping":
            templates = [
                f"What is the purpose of this project and what problem does it solve?",
                f"What are the main modules/components of this project?",
                f"What is the high-level architecture of this project?",
            ]
        elif phase == "Architecture Understanding":
            templates = [
                f"What architectural pattern does this project follow?",
                f"How are the main modules organized and how do they interact?",
                f"What are the key design decisions made in this project?",
            ]
        elif phase == "Use Cases & Scenarios":
            templates = [
                f"What is a typical usage scenario for this project?",
                f"What are the main user workflows in this project?",
            ]
        else:
            templates = []
        
        for i, template in enumerate(templates[:count]):
            questions.append({
                "phase": phase,
                "question_text": template,
                "target_files": [],
                "target_symbols": [],
                "importance_level": "medium",
            })
        
        return questions

    def _extract_question_from_response(self, response: str) -> str:
        """Extract a single question from LLM response.
        
        CRITICAL: This method ensures exactly ONE question is extracted.
        If the response contains multiple questions, only the first one is returned.
        """
        # Try to find the first question mark
        lines = response.strip().split("\n")
        for line in lines:
            line = line.strip()
            if "?" in line:
                # Extract only the first question (up to the first question mark)
                question_part = line.split("?")[0] + "?"
                # Remove markdown formatting
                question_part = re.sub(r'^[*#\-\d.]+\s*', '', question_part)
                question_part = question_part.strip()
                
                # Additional cleaning: remove any trailing content after the question mark
                # that might be part of another question
                if question_part:
                    return question_part
        
        # If no question mark found, return the first non-empty line
        for line in lines:
            line = line.strip()
            if line:
                # Remove markdown formatting
                question = re.sub(r'^[*#\-\d.]+\s*', '', line)
                return question.strip()
        
        return response.strip()
    
    def _ensure_single_question(self, question_text: str) -> str:
        """Ensure the question text contains exactly one question.
        
        If multiple questions are detected, extract only the first one.
        Also validates that the question is a single sentence.
        """
        # Split by question marks to detect multiple questions
        parts = question_text.split("?")
        
        if len(parts) > 2:  # More than one question mark
            # Extract only the first question
            first_question = parts[0].strip() + "?"
            # Clean up any leading/trailing whitespace or formatting
            first_question = re.sub(r'^[*#\-\d.]+\s*', '', first_question)
            return first_question.strip()
        
        # Check for multiple sentences that might be separate questions
        # Look for patterns like "How does X work? What about Y?"
        sentences = re.split(r'[.!?]+', question_text)
        if len(sentences) > 2:  # More than one sentence
            # Take only the first sentence that looks like a question
            for sentence in sentences:
                sentence = sentence.strip()
                if sentence and any(sentence.lower().startswith(q) for q in ['how', 'what', 'why', 'when', 'where', 'which', 'who']):
                    # Add question mark if missing
                    if not sentence.endswith('?'):
                        sentence += '?'
                    return sentence
        
        # If it's a single question, ensure it ends with a question mark
        if not question_text.strip().endswith('?'):
            question_text = question_text.strip() + '?'
        
        return question_text

    def _parse_multiple_questions(
        self,
        response: str,
        phase: str,
    ) -> list[dict[str, Any]]:
        """Parse multiple questions from LLM response."""
        questions = []
        
        # Split by question marks
        parts = response.split("?")
        
        for part in parts[:-1]:  # Exclude last part (after last ?)
            question_text = part.strip()
            
            # Clean up
            question_text = re.sub(r'^[*#\-\d.]+\s*', '', question_text)
            question_text = question_text.strip()
            
            if question_text:
                questions.append({
                    "phase": phase,
                    "question_text": question_text + "?",
                    "target_files": [],
                    "target_symbols": [],
                    "importance_level": "medium",
                })
        
        return questions

    def _validate_and_repair(
        self,
        questions: list[dict[str, Any]],
        analysis: dict[str, Any],
        total_questions: int,
        code_detail_ratio: float,
        min_core_file_coverage: float,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Validate and repair the generated question set.
        
        If questions are insufficient, automatically generate more to meet targets.
        Returns (repaired_questions, validation_result).
        """
        # First, perform validation
        validation_result = {
            "is_valid": True,
            "total_questions": len(questions),
            "code_detail_count": 0,
            "code_detail_ratio": 0.0,
            "core_files_detected": len(analysis.get("core_files", [])),
            "core_files_covered": 0,
            "core_file_coverage": 0.0,
            "phase_counts": {},
            "warnings": [],
            "errors": [],
            "repaired": False,
        }
        
        # Count questions by phase
        phase_counts = {}
        for q in questions:
            phase = q.get("phase", "Unknown")
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
        
        validation_result["phase_counts"] = phase_counts
        
        # Count code detail questions
        code_detail_count = phase_counts.get("Code Detail Completion", 0)
        validation_result["code_detail_count"] = code_detail_count
        
        # Calculate code detail ratio
        if len(questions) > 0:
            code_detail_ratio_actual = code_detail_count / len(questions)
            validation_result["code_detail_ratio"] = code_detail_ratio_actual
        else:
            code_detail_ratio_actual = 0
        
        # Check core file coverage
        core_files = set(f.get("path") for f in analysis.get("core_files", []))
        covered_files = set()
        for q in questions:
            covered_files.update(q.get("target_files", []))
        
        validation_result["core_files_covered"] = len(covered_files & core_files)
        
        if core_files:
            coverage = len(covered_files & core_files) / len(core_files)
            validation_result["core_file_coverage"] = coverage
        
        # REPAIR PHASE: Generate additional questions if needed
        needs_repair = False
        additional_questions = []
        
        # Calculate how many code detail questions we need
        target_code_detail = int(total_questions * code_detail_ratio)
        current_code_detail = code_detail_count
        code_detail_deficit = max(0, target_code_detail - current_code_detail)
        
        # Calculate total deficit
        total_deficit = max(0, total_questions - len(questions))
        
        if code_detail_deficit > 0 or total_deficit > 0:
            needs_repair = True
            
            # Generate additional code detail questions
            core_files_list = analysis.get("core_files", [])
            if core_files_list:
                # Determine how many more questions per file
                questions_to_generate = max(code_detail_deficit, total_deficit)
                
                # Generate using different angles for variety
                for i in range(questions_to_generate):
                    # Cycle through core files
                    file_info = core_files_list[i % len(core_files_list)]
                    
                    # Try each angle
                    angle_index = i % len(self.QUESTION_ANGLES)
                    angle = self.QUESTION_ANGLES[angle_index]
                    
                    question = self._generate_file_specific_question(
                        file_info, analysis, "high", angle=angle
                    )
                    if question:
                        additional_questions.append(question)
                
                # Deduplicate
                additional_questions = self._deduplicate_questions(additional_questions)
        
        # If we still need more questions (code detail ratio issue), adjust by adding panorama/arch questions
        if len(questions) + len(additional_questions) < total_questions:
            remaining = total_questions - len(questions) - len(additional_questions)
            
            # Add architecture questions
            arch_questions = self._generate_generic_phase_questions(
                "Architecture Understanding",
                {"count": min(3, remaining), "description": "Understand project architecture"},
                analysis,
                questions
            )
            additional_questions.extend(arch_questions[:remaining])
            remaining -= len(arch_questions)
            
            # Add panorama questions if still needed
            if remaining > 0:
                panorama_questions = self._generate_generic_phase_questions(
                    "Panorama Mapping",
                    {"count": min(2, remaining), "description": "Project overview"},
                    analysis,
                    questions
                )
                additional_questions.extend(panorama_questions[:remaining])
        
        # Merge additional questions
        if additional_questions:
            questions = questions + additional_questions
            validation_result["repaired"] = True
            validation_result["repaired_count"] = len(additional_questions)
        
        # Re-validate after repair
        phase_counts = {}
        for q in questions:
            phase = q.get("phase", "Unknown")
            phase_counts[phase] = phase_counts.get(phase, 0) + 1
        
        validation_result["total_questions"] = len(questions)
        validation_result["phase_counts"] = phase_counts
        validation_result["code_detail_count"] = phase_counts.get("Code Detail Completion", 0)
        
        if len(questions) > 0:
            validation_result["code_detail_ratio"] = validation_result["code_detail_count"] / len(questions)
        
        # Recalculate coverage
        covered_files = set()
        for q in questions:
            covered_files.update(q.get("target_files", []))
        validation_result["core_files_covered"] = len(covered_files & core_files)
        if core_files:
            validation_result["core_file_coverage"] = len(covered_files & core_files) / len(core_files)
        
        # Final warnings
        if validation_result["code_detail_ratio"] < code_detail_ratio:
            validation_result["warnings"].append(
                f"Code detail ratio ({validation_result['code_detail_ratio']:.2%}) still below target after repair"
            )
        
        if len(questions) < total_questions:
            validation_result["warnings"].append(
                f"Total questions ({len(questions)}) still below target after repair"
            )
        
        # Check for duplicates
        duplicates = self._find_duplicates(questions)
        if duplicates:
            validation_result["warnings"].append(f"Found {len(duplicates)} potential duplicate questions")
        
        # Set overall validity
        if validation_result["errors"]:
            validation_result["is_valid"] = False
        
        return questions, validation_result

    def _improve_coherence(self, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Improve coherence between questions.
        
        This method reorders questions within each phase to create a more natural flow.
        It also ensures questions build on each other logically.
        """
        if not questions:
            return questions
        
        # Group questions by phase
        phase_groups = {}
        for q in questions:
            phase = q.get("phase", "Unknown")
            if phase not in phase_groups:
                phase_groups[phase] = []
            phase_groups[phase].append(q)
        
        # Reorder questions within each phase for better flow
        improved_questions = []
        
        # Define the logical order of phases
        phase_order = [
            "Panorama Mapping",
            "Architecture Understanding", 
            "Code Detail Completion",
            "Use Cases & Scenarios"
        ]
        
        for phase in phase_order:
            if phase in phase_groups:
                phase_questions = phase_groups[phase]
                
                # For Code Detail Completion, sort by importance (high first)
                if phase == "Code Detail Completion":
                    # Sort by importance level: high > medium > low
                    importance_order = {"high": 0, "medium": 1, "low": 2}
                    phase_questions.sort(
                        key=lambda q: importance_order.get(q.get("importance_level", "medium"), 1)
                    )
                
                # For other phases, try to create a natural progression
                else:
                    # Simple heuristic: sort by question length (shorter first for overview)
                    # and ensure questions build on each other
                    phase_questions.sort(key=lambda q: len(q.get("question_text", "")))
                
                improved_questions.extend(phase_questions)
        
        # Add any questions with unknown phases at the end
        for phase, phase_questions in phase_groups.items():
            if phase not in phase_order:
                improved_questions.extend(phase_questions)
        
        return improved_questions

    def _find_duplicates(self, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find duplicate or near-duplicate questions."""
        duplicates = []
        
        # Normalize questions for comparison
        normalized = []
        for q in questions:
            text = q.get("question_text", "").lower()
            # Remove common prefixes
            text = re.sub(r'^(how|what|why|when|where|which|who)\s+', '', text)
            # Remove punctuation
            text = re.sub(r'[^\w\s]', '', text)
            normalized.append(text)
        
        # Compare each pair
        for i in range(len(normalized)):
            for j in range(i + 1, len(normalized)):
                similarity = self._calculate_similarity(normalized[i], normalized[j])
                if similarity > 0.8:  # 80% similarity threshold
                    duplicates.append({
                        "question1_index": i,
                        "question2_index": j,
                        "similarity": similarity,
                    })
        
        return duplicates

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        # Simple word overlap similarity (Jaccard + containment)
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        jaccard = len(intersection) / len(union)
        # Also check containment: if one is mostly contained in the other
        containment = len(intersection) / min(len(words1), len(words2)) if min(len(words1), len(words2)) > 0 else 0.0
        
        return max(jaccard, containment)

    def _find_modification_questions(self, questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Find questions that ask for modifications."""
        modification_patterns = [
            r'how should .* be (changed|modified|improved|refactored)',
            r'what files need (to be )?(changed|modified|updated)',
            r'how would you (refactor|improve|change)',
            r'what (improvement|change|modification)',
            r'how to (improve|optimize|enhance)',
        ]
        
        modification_questions = []
        
        for q in questions:
            text = q.get("question_text", "").lower()
            for pattern in modification_patterns:
                if re.search(pattern, text):
                    modification_questions.append(q)
                    break
        
        return modification_questions

    def _generate_coverage_report(
        self,
        questions: list[dict[str, Any]],
        analysis: dict[str, Any],
        min_core_file_coverage: float,
    ) -> dict[str, Any]:
        """Generate a coverage report."""
        core_files = analysis.get("core_files", [])
        
        # Track coverage
        file_importance = {}
        for f in core_files:
            file_importance[f.get("path")] = f.get("importance", 0.0)
        
        covered_files = set()
        for q in questions:
            covered_files.update(q.get("target_files", []))
        
        core_file_paths = set(f.get("path") for f in core_files)
        covered_core_files = covered_files & core_file_paths
        uncovered_core_files = core_file_paths - covered_files
        
        coverage_percentage = len(covered_core_files) / len(core_file_paths) if core_file_paths else 0.0
        
        return {
            "total_core_files": len(core_file_paths),
            "covered_core_files": len(covered_core_files),
            "coverage_percentage": coverage_percentage,
            "uncovered_files": list(uncovered_core_files),
            "file_importance": file_importance,
            "meets_target": coverage_percentage >= min_core_file_coverage,
        }


# Singleton instance
question_set_generator = QuestionSetGenerator()
