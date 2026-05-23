"""
Enhanced Repository Analyzer Service

Inspired by CodeGraph's approach to code understanding:
- Tree-sitter-like AST parsing using regex patterns
- Dependency graph construction
- Importance scoring based on references and centrality
- Framework route pattern recognition

Analyzes a repository to understand its structure, extract symbols,
build relationships, and prepare for high-quality question generation.
"""

import os
import re
import json
from pathlib import Path
from typing import Any
from collections import defaultdict


class EnhancedRepositoryAnalyzer:
    """Enhanced analyzer with symbol extraction and relationship graph."""

    # File extensions to consider as code files
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".hpp",
        ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".kts", ".scala", ".cs",
    }

    # Directories to exclude from analysis
    EXCLUDED_DIRS = {
        "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
        "dist", "build", ".next", ".nuxt", "target", "vendor", "packages",
        ".idea", ".vscode", ".cache", ".temp", ".tmp", ".codegraph",
    }

    # Files to exclude
    EXCLUDED_FILES = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock",
        "Cargo.lock", "go.sum", "composer.lock", "poetry.lock",
        ".gitignore", ".gitattributes", ".editorconfig",
        "LICENSE", "LICENCE", "CONTRIBUTING.md",
    }

    # Framework route patterns
    ROUTE_PATTERNS = {
        "python": [
            # Flask
            (r'@\w+\.route\(["\']([^"\']+)["\']', "flask"),
            # FastAPI
            (r'@\w+\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']', "fastapi"),
            # Django
            (r'path\(["\']([^"\']+)["\']', "django"),
            (r'url\(["\']([^"\']+)["\']', "django"),
        ],
        "javascript": [
            # Express
            (r'(?:app|router)\.(get|post|put|delete|patch|use)\(["\']([^"\']+)["\']', "express"),
            # Next.js API routes
            (r'export\s+(?:default\s+)?(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)', "nextjs"),
        ],
        "typescript": [
            # Express/TS
            (r'(?:app|router)\.(get|post|put|delete|patch|use)\(["\']([^"\']+)["\']', "express"),
            # NestJS
            (r'@(Get|Post|Put|Delete|Patch)\(["\']([^"\']+)["\']', "nestjs"),
            # Next.js
            (r'export\s+(?:const|async\s+function)\s+(GET|POST|PUT|DELETE|PATCH)', "nextjs"),
        ],
    }

    def __init__(self):
        self.repo_path: Path | None = None
        self.analysis: dict[str, Any] = {}
        self.symbols: dict[str, list[dict]] = defaultdict(list)  # symbol_type -> list of symbols
        self.relationships: dict[str, list[dict]] = defaultdict(list)  # rel_type -> list of relationships
        self.file_references: dict[str, set] = defaultdict(set)  # file -> set of referenced files

    def analyze_repository(self, repo_path: Path) -> dict[str, Any]:
        """
        Analyze a repository with enhanced symbol extraction and relationship graph.
        
        Args:
            repo_path: Path to the repository
            
        Returns:
            Dictionary containing comprehensive analysis
        """
        self.repo_path = repo_path
        
        try:
            # Phase 1: Extract all symbols
            self._extract_all_symbols()
            
            # Phase 2: Build relationship graph
            self._build_relationship_graph()
            
            # Phase 3: Identify routes and endpoints
            self._identify_routes()
            
            # Phase 4: Calculate importance scores
            importance_scores = self._calculate_importance_scores()
            
            # Phase 5: Identify architectural patterns
            architectural_patterns = self._identify_architectural_patterns()
            
            # Phase 6: Generate analysis summary
            self.analysis = {
                "repository_path": str(self.repo_path),
                "languages": self._detect_languages(),
                "frameworks": self._detect_frameworks(),
                "top_level_structure": self._get_top_level_structure(),
                "entrypoints": self._find_entrypoints(),
                "symbols": {
                    "classes": self.symbols.get("classes", []),
                    "functions": self.symbols.get("functions", []),
                    "methods": self.symbols.get("methods", []),
                    "interfaces": self.symbols.get("interfaces", []),
                    "constants": self.symbols.get("constants", []),
                },
                "relationships": {
                    "imports": self.relationships.get("imports", []),
                    "calls": self.relationships.get("calls", []),
                    "inherits": self.relationships.get("inherits", []),
                    "implements": self.relationships.get("implements", []),
                    "uses": self.relationships.get("uses", []),
                },
                "routes": self.relationships.get("routes", []),
                "core_files": self._identify_core_files(importance_scores),
                "dependency_graph": self._build_dependency_summary(),
                "architectural_patterns": architectural_patterns,
                "entry_point_flow": self._trace_entry_point_flow(),
            }
            
            return self.analysis
            
        finally:
            # Reset state
            self.symbols.clear()
            self.relationships.clear()
            self.file_references.clear()

    def _extract_all_symbols(self):
        """Extract all symbols from the repository."""
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()
                
                if ext not in self.CODE_EXTENSIONS:
                    continue
                    
                if file in self.EXCLUDED_FILES:
                    continue
                
                try:
                    content = file_path.read_text(errors="ignore")
                    rel_path = str(file_path.relative_to(self.repo_path))
                    
                    # Extract symbols based on language
                    if ext == ".py":
                        self._extract_python_symbols(content, rel_path)
                    elif ext in {".js", ".ts", ".tsx", ".jsx"}:
                        self._extract_javascript_symbols(content, rel_path)
                    elif ext == ".java":
                        self._extract_java_symbols(content, rel_path)
                    elif ext == ".go":
                        self._extract_go_symbols(content, rel_path)
                        
                except Exception:
                    continue

    def _extract_python_symbols(self, content: str, file_path: str):
        """Extract Python symbols."""
        lines = content.split("\n")
        
        # Extract imports
        import_pattern = r'^(?:from\s+(\S+)\s+)?import\s+(\S+)(?:\s+as\s+(\S+))?'
        for match in re.finditer(import_pattern, content, re.MULTILINE):
            module = match.group(1) or ""
            name = match.group(2)
            alias = match.group(3)
            
            self.relationships["imports"].append({
                "file": file_path,
                "module": module,
                "name": name,
                "alias": alias,
                "line": content[:match.start()].count("\n") + 1,
            })
        
        # Extract classes with inheritance
        class_pattern = r'^class\s+(\w+)(?:\(([^)]*)\))?:'
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            class_name = match.group(1)
            bases = match.group(2)
            
            self.symbols["classes"].append({
                "name": class_name,
                "file": file_path,
                "line": content[:match.start()].count("\n") + 1,
                "bases": [b.strip() for b in bases.split(",")] if bases else [],
            })
            
            # Record inheritance relationships
            if bases:
                for base in bases.split(","):
                    base = base.strip()
                    if base and base != "object":
                        self.relationships["inherits"].append({
                            "child": class_name,
                            "parent": base,
                            "file": file_path,
                        })
        
        # Extract functions and methods
        func_pattern = r'^(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*[^:]+)?:'
        for match in re.finditer(func_pattern, content, re.MULTILINE):
            func_name = match.group(1)
            params = match.group(2)
            
            # Check if it's a method (inside a class context)
            # Simple heuristic: check indentation
            line_start = content[:match.start()].count("\n")
            if line_start > 0:
                prev_lines = lines[max(0, line_start-10):line_start]
                is_method = any(line.strip().startswith("class ") and not line.strip().startswith("class ") 
                               for line in prev_lines if line.strip())
            else:
                is_method = False
            
            symbol_type = "methods" if is_method else "functions"
            
            self.symbols[symbol_type].append({
                "name": func_name,
                "file": file_path,
                "line": line_start + 1,
                "params": [p.strip().split(":")[0].strip() for p in params.split(",") if p.strip()],
                "is_async": "async" in content[match.start()-10:match.start()],
            })
        
        # Extract function calls
        call_pattern = r'(\w+)\s*\('
        for match in re.finditer(call_pattern, content):
            call_name = match.group(1)
            if call_name in {"if", "for", "while", "with", "def", "class", "return", "import", "from"}:
                continue
            
            self.relationships["calls"].append({
                "caller": file_path,
                "callee": call_name,
                "line": content[:match.start()].count("\n") + 1,
            })

    def _extract_javascript_symbols(self, content: str, file_path: str):
        """Extract JavaScript/TypeScript symbols."""
        # Extract imports
        import_patterns = [
            r'import\s+(?:{[^}]+}|\w+)\s+from\s+["\']([^"\']+)["\']',
            r'require\s*\(\s*["\']([^"\']+)["\']\s*\)',
            r'import\s+["\']([^"\']+)["\']',
        ]
        
        for pattern in import_patterns:
            for match in re.finditer(pattern, content):
                module = match.group(1)
                self.relationships["imports"].append({
                    "file": file_path,
                    "module": module,
                    "line": content[:match.start()].count("\n") + 1,
                })
        
        # Extract classes
        class_pattern = r'class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?'
        for match in re.finditer(class_pattern, content):
            class_name = match.group(1)
            parent = match.group(2)
            interfaces = match.group(3)
            
            self.symbols["classes"].append({
                "name": class_name,
                "file": file_path,
                "line": content[:match.start()].count("\n") + 1,
                "parent": parent,
                "interfaces": [i.strip() for i in interfaces.split(",")] if interfaces else [],
            })
            
            if parent:
                self.relationships["inherits"].append({
                    "child": class_name,
                    "parent": parent,
                    "file": file_path,
                })
            
            if interfaces:
                for interface in interfaces.split(","):
                    interface = interface.strip()
                    if interface:
                        self.relationships["implements"].append({
                            "class": class_name,
                            "interface": interface,
                            "file": file_path,
                        })
        
        # Extract functions
        func_patterns = [
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
            r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function',
        ]
        
        for pattern in func_patterns:
            for match in re.finditer(pattern, content):
                func_name = match.group(1)
                params = match.group(2) if match.lastindex >= 2 else ""
                
                self.symbols["functions"].append({
                    "name": func_name,
                    "file": file_path,
                    "line": content[:match.start()].count("\n") + 1,
                    "params": [p.strip().split(":")[0].strip().split("=")[0].strip() 
                              for p in params.split(",") if p.strip()],
                })
        
        # Extract method definitions
        method_pattern = r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*\w+)?\s*{'
        for match in re.finditer(method_pattern, content):
            method_name = match.group(1)
            if method_name in {"if", "for", "while", "switch", "catch", "function", "class", "return"}:
                continue
            
            self.symbols["methods"].append({
                "name": method_name,
                "file": file_path,
                "line": content[:match.start()].count("\n") + 1,
            })

    def _extract_java_symbols(self, content: str, file_path: str):
        """Extract Java symbols."""
        # Extract class/interface declarations
        class_pattern = r'(?:public\s+)?(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?'
        for match in re.finditer(class_pattern, content):
            name = match.group(1)
            parent = match.group(2)
            interfaces = match.group(3)
            
            is_interface = "interface" in match.group(0)
            symbol_type = "interfaces" if is_interface else "classes"
            
            self.symbols[symbol_type].append({
                "name": name,
                "file": file_path,
                "line": content[:match.start()].count("\n") + 1,
            })
            
            if parent:
                self.relationships["inherits"].append({
                    "child": name,
                    "parent": parent,
                    "file": file_path,
                })
            
            if interfaces:
                for interface in interfaces.split(","):
                    interface = interface.strip()
                    if interface:
                        self.relationships["implements"].append({
                            "class": name,
                            "interface": interface,
                            "file": file_path,
                        })
        
        # Extract methods
        method_pattern = r'(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(([^)]*)\)'
        for match in re.finditer(method_pattern, content):
            method_name = match.group(1)
            if method_name in {"if", "for", "while", "switch", "catch", "return", "new"}:
                continue
            
            self.symbols["methods"].append({
                "name": method_name,
                "file": file_path,
                "line": content[:match.start()].count("\n") + 1,
            })

    def _extract_go_symbols(self, content: str, file_path: str):
        """Extract Go symbols."""
        # Extract imports
        import_pattern = r'import\s+(?:\(\s*([^)]+)\)|"([^"]+)")'
        for match in re.finditer(import_pattern, content, re.DOTALL):
            imports_block = match.group(1) or match.group(2)
            if imports_block:
                for imp in re.findall(r'"([^"]+)"', imports_block):
                    self.relationships["imports"].append({
                        "file": file_path,
                        "module": imp,
                        "line": content[:match.start()].count("\n") + 1,
                    })
        
        # Extract struct types (similar to classes)
        struct_pattern = r'type\s+(\w+)\s+struct\s*\{'
        for match in re.finditer(struct_pattern, content):
            struct_name = match.group(1)
            self.symbols["classes"].append({
                "name": struct_name,
                "file": file_path,
                "line": content[:match.start()].count("\n") + 1,
            })
        
        # Extract functions
        func_pattern = r'func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(([^)]*)\)'
        for match in re.finditer(func_pattern, content):
            func_name = match.group(1)
            self.symbols["functions"].append({
                "name": func_name,
                "file": file_path,
                "line": content[:match.start()].count("\n") + 1,
            })

    def _build_relationship_graph(self):
        """Build relationship graph from imports and references."""
        # Build file reference map from imports
        for import_info in self.relationships["imports"]:
            source_file = import_info["file"]
            module = import_info.get("module", "")
            
            # Try to resolve module to file path
            if module:
                # Handle relative imports
                if module.startswith("."):
                    source_dir = Path(source_file).parent
                    resolved = self._resolve_relative_import(source_dir, module)
                    if resolved:
                        self.file_references[source_file].add(resolved)
                else:
                    # Try to find the module in the repository
                    resolved = self._resolve_absolute_import(module)
                    if resolved:
                        self.file_references[source_file].add(resolved)
        
        # Build call relationships
        # Group calls by file and resolve to symbols
        calls_by_file = defaultdict(list)
        for call in self.relationships["calls"]:
            calls_by_file[call["caller"]].append(call)
        
        # Try to resolve calls to actual function definitions
        all_functions = {f["name"]: f for f in self.symbols["functions"]}
        all_methods = {m["name"]: m for m in self.symbols["methods"]}
        
        for caller_file, calls in calls_by_file.items():
            for call in calls:
                callee_name = call["callee"]
                
                # Check if it's a known function
                if callee_name in all_functions:
                    callee_file = all_functions[callee_name]["file"]
                    if callee_file != caller_file:
                        self.file_references[caller_file].add(callee_file)
                        self.relationships["uses"].append({
                            "user": caller_file,
                            "uses": callee_name,
                            "defined_in": callee_file,
                        })

    def _resolve_relative_import(self, source_dir: Path, module: str) -> str | None:
        """Resolve a relative import to a file path."""
        # Remove leading dots
        dots = len(module) - len(module.lstrip("."))
        module_path = module.lstrip(".")
        
        # Go up directories based on dots
        current_dir = source_dir
        for _ in range(dots - 1):
            current_dir = current_dir.parent
        
        # Convert module path to file path
        parts = module_path.split(".")
        potential_path = current_dir / "/".join(parts)
        
        # Check various extensions
        for ext in [".py", ".js", ".ts", "/__init__.py", "/index.js", "/index.ts"]:
            candidate = potential_path.with_suffix(ext) if ext.startswith(".") else potential_path / ext.lstrip("/")
            if candidate.exists():
                return str(candidate.relative_to(self.repo_path))
        
        return None

    def _resolve_absolute_import(self, module: str) -> str | None:
        """Resolve an absolute import to a file path."""
        # Handle common patterns
        parts = module.split(".")
        
        # Try direct path
        potential_path = self.repo_path / "/".join(parts)
        for ext in [".py", ".js", ".ts", "/__init__.py", "/index.js", "/index.ts"]:
            candidate = potential_path.with_suffix(ext) if ext.startswith(".") else potential_path / ext.lstrip("/")
            if candidate.exists():
                return str(candidate.relative_to(self.repo_path))
        
        return None

    def _identify_routes(self):
        """Identify framework routes and endpoints."""
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()
                
                if ext not in self.CODE_EXTENSIONS:
                    continue
                
                try:
                    content = file_path.read_text(errors="ignore")
                    rel_path = str(file_path.relative_to(self.repo_path))
                    
                    # Get language from extension
                    lang_map = {".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript"}
                    lang = lang_map.get(ext)
                    
                    if lang and lang in self.ROUTE_PATTERNS:
                        for pattern, framework in self.ROUTE_PATTERNS[lang]:
                            for match in re.finditer(pattern, content):
                                groups = match.groups()
                                method = groups[0] if len(groups) > 1 else "GET"
                                path = groups[-1] if len(groups) > 0 else groups[0]
                                
                                # Get the handler function name
                                line_num = content[:match.start()].count("\n")
                                lines = content.split("\n")
                                handler_line = lines[min(line_num + 1, len(lines) - 1)]
                                
                                # Extract function name after the decorator
                                func_match = re.search(r'(?:async\s+)?def\s+(\w+)', handler_line)
                                handler = func_match.group(1) if func_match else "unknown"
                                
                                self.relationships["routes"].append({
                                    "file": rel_path,
                                    "method": method.upper() if method.isalpha() else "GET",
                                    "path": path,
                                    "handler": handler,
                                    "framework": framework,
                                    "line": line_num + 1,
                                })
                                
                except Exception:
                    continue

    def _calculate_importance_scores(self) -> dict[str, float]:
        """Calculate importance scores for each file."""
        scores = defaultdict(float)
        
        # Count incoming references (being imported/used by others)
        for source, targets in self.file_references.items():
            for target in targets:
                scores[target] += 0.3
        
        # Count symbols defined
        for symbol_type in ["classes", "functions", "methods"]:
            for symbol in self.symbols[symbol_type]:
                scores[symbol["file"]] += 0.2
        
        # Count routes
        for route in self.relationships["routes"]:
            scores[route["file"]] += 0.5
        
        # Bonus for entrypoints
        entrypoints = self._find_entrypoints()
        for ep in entrypoints:
            scores[ep["file"]] += 0.4
        
        # Normalize scores
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                scores = {k: v / max_score for k, v in scores.items()}
        
        return dict(scores)

    def _identify_core_files(self, importance_scores: dict[str, float]) -> list[dict[str, Any]]:
        """Identify core files based on importance scores."""
        core_files = []
        
        for file_path, score in importance_scores.items():
            if score > 0.3:  # Threshold for core files
                full_path = self.repo_path / file_path
                core_files.append({
                    "path": file_path,
                    "importance": round(score, 3),
                    "size": full_path.stat().st_size if full_path.exists() else 0,
                    "symbols_count": sum(
                        1 for symbols in self.symbols.values()
                        for s in symbols if s["file"] == file_path
                    ),
                    "incoming_refs": sum(
                        1 for targets in self.file_references.values()
                        if file_path in targets
                    ),
                })
        
        # Sort by importance
        core_files.sort(key=lambda x: x["importance"], reverse=True)
        
        return core_files

    def _build_dependency_summary(self) -> dict[str, Any]:
        """Build dependency graph summary."""
        # Find files with most incoming dependencies (most depended upon)
        incoming = defaultdict(int)
        outgoing = defaultdict(int)
        
        for source, targets in self.file_references.items():
            outgoing[source] += len(targets)
            for target in targets:
                incoming[target] += 1
        
        # Find highly connected files
        highly_depended = sorted(incoming.items(), key=lambda x: x[1], reverse=True)[:10]
        highly_depending = sorted(outgoing.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "highly_depended_upon": [{"file": f, "count": c} for f, c in highly_depended],
            "highly_depending": [{"file": f, "count": c} for f, c in highly_depending],
            "total_relationships": sum(len(rels) for rels in self.relationships.values()),
        }

    def _identify_architectural_patterns(self) -> list[str]:
        """Identify architectural patterns in the codebase."""
        patterns = []
        
        # Check for MVC pattern
        has_models = any("model" in f["file"].lower() for f in self.symbols["classes"])
        has_views = any("view" in f["file"].lower() for f in self.symbols["classes"])
        has_controllers = any("controller" in f["file"].lower() for f in self.symbols["classes"])
        
        if has_models and has_views:
            patterns.append("MVC")
        if has_models and has_controllers:
            patterns.append("MVC-like")
        
        # Check for repository pattern
        has_repositories = any("repository" in f["file"].lower() or "repo" in f["file"].lower() 
                            for f in self.symbols["classes"])
        if has_repositories:
            patterns.append("Repository Pattern")
        
        # Check for service layer
        has_services = any("service" in f["file"].lower() for f in self.symbols["classes"])
        if has_services:
            patterns.append("Service Layer")
        
        # Check for dependency injection
        has_di = any("inject" in f["file"].lower() or "container" in f["file"].lower() 
                    for f in self.symbols["classes"])
        if has_di:
            patterns.append("Dependency Injection")
        
        # Check for API routes
        if self.relationships["routes"]:
            patterns.append("REST API")
        
        # Check for event-driven
        has_events = any("event" in f["file"].lower() or "listener" in f["file"].lower() 
                        for f in self.symbols["classes"])
        if has_events:
            patterns.append("Event-Driven")
        
        return patterns

    def _trace_entry_point_flow(self) -> list[dict[str, Any]]:
        """Trace the flow from entry points."""
        flows = []
        
        entrypoints = self._find_entrypoints()
        
        for ep in entrypoints:
            flow = {
                "entrypoint": ep["file"],
                "direct_calls": [],
                "dependencies": [],
            }
            
            # Find direct calls from entrypoint
            for call in self.relationships["calls"]:
                if call["caller"] == ep["file"]:
                    flow["direct_calls"].append(call["callee"])
            
            # Find direct dependencies
            if ep["file"] in self.file_references:
                flow["dependencies"] = list(self.file_references[ep["file"]])
            
            flows.append(flow)
        
        return flows

    # Helper methods (similar to original but enhanced)
    def _detect_languages(self) -> dict[str, int]:
        """Detect programming languages used in the repository."""
        language_counts: dict[str, int] = {}
        
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                ext = Path(file).suffix.lower()
                if ext in self.CODE_EXTENSIONS:
                    language_counts[ext] = language_counts.get(ext, 0) + 1
        
        return language_counts

    def _detect_frameworks(self) -> list[str]:
        """Detect frameworks used in the repository."""
        frameworks = []
        
        # Check package.json for JS/TS frameworks
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            import json
            with open(package_json) as f:
                data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                
                framework_map = {
                    "react": "React", "vue": "Vue", "@angular/core": "Angular",
                    "next": "Next.js", "nuxt": "Nuxt.js", "express": "Express",
                    "fastify": "Fastify", "vite": "Vite", "@nestjs/core": "NestJS",
                }
                
                for dep, name in framework_map.items():
                    if dep in deps:
                        frameworks.append(name)
        
        # Check Python frameworks
        requirements_txt = self.repo_path / "requirements.txt"
        pyproject_toml = self.repo_path / "pyproject.toml"
        
        for config_file in [requirements_txt, pyproject_toml]:
            if config_file.exists():
                content = config_file.read_text().lower()
                framework_map = {
                    "django": "Django", "flask": "Flask", "fastapi": "FastAPI",
                    "langchain": "LangChain", "langgraph": "LangGraph",
                    "pyramid": "Pyramid", "tornado": "Tornado",
                }
                
                for dep, name in framework_map.items():
                    if dep in content and name not in frameworks:
                        frameworks.append(name)
        
        return list(set(frameworks))

    def _get_top_level_structure(self) -> list[dict[str, Any]]:
        """Get top-level directory structure."""
        structure = []
        
        for item in sorted(self.repo_path.iterdir()):
            if item.name.startswith("."):
                continue
            
            entry = {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "path": str(item.relative_to(self.repo_path)),
            }
            
            if item.is_dir():
                file_count = sum(1 for _ in item.rglob("*") if _.is_file())
                entry["file_count"] = file_count
            
            structure.append(entry)
        
        return structure

    def _find_entrypoints(self) -> list[dict[str, str]]:
        """Find main entrypoints of the application."""
        entrypoints = []
        
        entrypoint_patterns = [
            "main.py", "app.py", "server.py", "index.py",
            "main.js", "index.js", "server.js", "app.js",
            "main.ts", "index.ts", "server.ts", "app.ts",
            "main.tsx", "index.tsx", "App.tsx",
            "main.go", "cmd/main.go",
            "Main.java", "Application.java",
        ]
        
        for pattern in entrypoint_patterns:
            for file in self.repo_path.rglob(pattern):
                if file.is_file() and not any(excluded in str(file) for excluded in self.EXCLUDED_DIRS):
                    entrypoints.append({
                        "file": str(file.relative_to(self.repo_path)),
                        "type": "entrypoint",
                        "pattern": pattern,
                    })
        
        return entrypoints


# Singleton instance
enhanced_repository_analyzer = EnhancedRepositoryAnalyzer()
