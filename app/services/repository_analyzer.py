"""
Repository Analyzer Service

Analyzes a repository to understand its structure, detect core files,
and prepare for question generation.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.core.config import settings


class RepositoryAnalyzer:
    """Analyzes a repository to extract structure and core file information."""

    # File extensions to consider as code files
    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".hpp",
        ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".kts", ".scala", ".cs",
        ".vue", ".svelte", ".html", ".css", ".scss", ".less",
    }

    # Directories to exclude from analysis
    EXCLUDED_DIRS = {
        "node_modules", ".git", "__pycache__", ".venv", "venv", "env",
        "dist", "build", ".next", ".nuxt", "target", "vendor", "packages",
        ".idea", ".vscode", ".cache", ".temp", ".tmp",
    }

    # Files to exclude
    EXCLUDED_FILES = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock",
        "Cargo.lock", "go.sum", "composer.lock", "poetry.lock",
        ".gitignore", ".gitattributes", ".editorconfig",
        "LICENSE", "LICENCE", "CONTRIBUTING.md",
    }

    def __init__(self):
        self.repo_path: Path | None = None
        self.analysis: dict[str, Any] = {}

    def analyze_repository(self, repo_url: str, ref: str | None = None) -> dict[str, Any]:
        """
        Analyze a repository and return comprehensive analysis.
        
        Args:
            repo_url: URL of the git repository
            ref: Optional git ref (branch, tag, commit)
            
        Returns:
            Dictionary containing repository analysis
        """
        # Clone repository to temporary directory
        self.repo_path = self._clone_repository(repo_url, ref)
        
        try:
            # Perform analysis
            self.analysis = {
                "repository_url": repo_url,
                "ref": ref,
                "local_path": str(self.repo_path),
                "languages": self._detect_languages(),
                "frameworks": self._detect_frameworks(),
                "top_level_structure": self._get_top_level_structure(),
                "entrypoints": self._find_entrypoints(),
                "core_files": self._identify_core_files(),
                "core_classes": self._extract_core_classes(),
                "core_functions": self._extract_core_functions(),
                "data_config_files": self._find_data_config_files(),
                "test_files": self._find_test_files(),
                "dependency_info": self._extract_dependency_info(),
                "call_paths": self._identify_call_paths(),
                "excluded_files": self._get_excluded_files_with_reasons(),
            }
            
            return self.analysis
            
        finally:
            # Cleanup temporary directory
            if self.repo_path and self.repo_path.exists():
                import shutil
                shutil.rmtree(self.repo_path, ignore_errors=True)

    def _clone_repository(self, repo_url: str, ref: str | None = None) -> Path:
        """Clone repository to temporary directory."""
        temp_dir = tempfile.mkdtemp(prefix="repo_analysis_")
        repo_path = Path(temp_dir) / "repo"
        
        try:
            # Clone with minimal depth for speed
            cmd = ["git", "clone", "--depth", "1"]
            if ref:
                cmd.extend(["--branch", ref])
            cmd.extend([repo_url, str(repo_path)])
            
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout
            )
            
            return repo_path
            
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to clone repository: {e.stderr}")
        except subprocess.TimeoutExpired:
            raise ValueError("Repository clone timed out")

    def _detect_languages(self) -> dict[str, int]:
        """Detect programming languages used in the repository."""
        language_counts: dict[str, int] = {}
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip excluded directories
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
                
                if "react" in deps:
                    frameworks.append("React")
                if "vue" in deps:
                    frameworks.append("Vue")
                if "angular" in deps or "@angular/core" in deps:
                    frameworks.append("Angular")
                if "next" in deps:
                    frameworks.append("Next.js")
                if "nuxt" in deps:
                    frameworks.append("Nuxt.js")
                if "express" in deps:
                    frameworks.append("Express")
                if "fastify" in deps:
                    frameworks.append("Fastify")
                if "vite" in deps:
                    frameworks.append("Vite")
        
        # Check requirements.txt or pyproject.toml for Python frameworks
        requirements_txt = self.repo_path / "requirements.txt"
        pyproject_toml = self.repo_path / "pyproject.toml"
        
        if requirements_txt.exists():
            content = requirements_txt.read_text().lower()
            if "django" in content:
                frameworks.append("Django")
            if "flask" in content:
                frameworks.append("Flask")
            if "fastapi" in content:
                frameworks.append("FastAPI")
            if "langchain" in content:
                frameworks.append("LangChain")
            if "langgraph" in content:
                frameworks.append("LangGraph")
        
        if pyproject_toml.exists():
            content = pyproject_toml.read_text().lower()
            if "django" in content:
                frameworks.append("Django")
            if "flask" in content:
                frameworks.append("Flask")
            if "fastapi" in content:
                frameworks.append("FastAPI")
            if "langchain" in content:
                frameworks.append("LangChain")
            if "langgraph" in content:
                frameworks.append("LangGraph")
        
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
                # Count files in directory
                file_count = sum(1 for _ in item.rglob("*") if _.is_file())
                entry["file_count"] = file_count
            
            structure.append(entry)
        
        return structure

    def _find_entrypoints(self) -> list[dict[str, str]]:
        """Find main entrypoints of the application."""
        entrypoints = []
        
        # Common entrypoint patterns
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

    def _identify_core_files(self) -> list[dict[str, Any]]:
        """Identify core files in the repository."""
        core_files = []
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.repo_path)
                
                # Skip excluded files
                if file in self.EXCLUDED_FILES:
                    continue
                
                # Skip non-code files (unless they're config files)
                ext = file_path.suffix.lower()
                if ext not in self.CODE_EXTENSIONS and ext not in {".json", ".yaml", ".yml", ".toml"}:
                    continue
                
                # Calculate importance score
                importance = self._calculate_file_importance(file_path)
                
                if importance > 0.3:  # Threshold for core files
                    core_files.append({
                        "path": str(rel_path),
                        "importance": importance,
                        "language": ext,
                        "size": file_path.stat().st_size if file_path.exists() else 0,
                    })
        
        # Sort by importance
        core_files.sort(key=lambda x: x["importance"], reverse=True)
        
        return core_files

    def _calculate_file_importance(self, file_path: Path) -> float:
        """Calculate importance score for a file."""
        importance = 0.0
        
        try:
            content = file_path.read_text(errors="ignore")
            lines = content.split("\n")
            
            # Base score by file size
            line_count = len(lines)
            if line_count > 100:
                importance += 0.3
            elif line_count > 50:
                importance += 0.2
            elif line_count > 20:
                importance += 0.1
            
            # Check for class definitions
            class_count = sum(1 for line in lines if line.strip().startswith("class "))
            importance += min(class_count * 0.1, 0.3)
            
            # Check for function definitions
            func_count = sum(1 for line in lines if line.strip().startswith("def ") or line.strip().startswith("function "))
            importance += min(func_count * 0.05, 0.2)
            
            # Check for imports (indicates being imported by others)
            import_count = sum(1 for line in lines if "import" in line or "from" in line)
            importance += min(import_count * 0.02, 0.2)
            
            # Check for common important patterns
            important_patterns = [
                "class ", "def ", "function ", "async def", "async function",
                "export default", "export class", "export function",
                "app = ", "router = ", "server = ",
            ]
            for pattern in important_patterns:
                if pattern in content:
                    importance += 0.05
            
            # Normalize to 0-1 range
            importance = min(importance, 1.0)
            
        except Exception:
            importance = 0.1  # Default for unreadable files
        
        return importance

    def _extract_core_classes(self) -> list[dict[str, Any]]:
        """Extract core classes from the repository."""
        classes = []
        
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                if not file.endswith((".py", ".js", ".ts", ".tsx", ".jsx", ".java")):
                    continue
                
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(errors="ignore")
                    
                    # Simple class extraction (works for Python, JS, TS, Java)
                    import re
                    class_pattern = r'class\s+(\w+)'
                    for match in re.finditer(class_pattern, content):
                        class_name = match.group(1)
                        classes.append({
                            "name": class_name,
                            "file": str(file_path.relative_to(self.repo_path)),
                        })
                except Exception:
                    continue
        
        return classes

    def _extract_core_functions(self) -> list[dict[str, Any]]:
        """Extract core functions from the repository."""
        functions = []
        
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                if not file.endswith((".py", ".js", ".ts", ".tsx", ".jsx")):
                    continue
                
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(errors="ignore")
                    
                    # Simple function extraction
                    import re
                    func_pattern = r'(?:async\s+)?(?:def|function)\s+(\w+)'
                    for match in re.finditer(func_pattern, content):
                        func_name = match.group(1)
                        functions.append({
                            "name": func_name,
                            "file": str(file_path.relative_to(self.repo_path)),
                        })
                except Exception:
                    continue
        
        return functions

    def _find_data_config_files(self) -> list[dict[str, str]]:
        """Find data and configuration files."""
        config_files = []
        
        config_patterns = [
            "*.json", "*.yaml", "*.yml", "*.toml", "*.env", "*.env.*",
            "*.config.*", "config.*", "settings.*",
        ]
        
        for pattern in config_patterns:
            for file in self.repo_path.rglob(pattern):
                if file.is_file() and not any(excluded in str(file) for excluded in self.EXCLUDED_DIRS):
                    config_files.append({
                        "path": str(file.relative_to(self.repo_path)),
                        "type": "config",
                    })
        
        return config_files

    def _find_test_files(self) -> list[dict[str, str]]:
        """Find test files."""
        test_files = []
        
        test_patterns = [
            "*test*.py", "*_test.py", "test_*.py",
            "*test*.js", "*_test.js", "test_*.js",
            "*test*.ts", "*_test.ts", "test_*.ts",
            "*spec*.py", "*_spec.py", "spec_*.py",
            "*spec*.js", "*_spec.js", "spec_*.js",
            "*spec*.ts", "*_spec.ts", "spec_*.ts",
        ]
        
        for pattern in test_patterns:
            for file in self.repo_path.rglob(pattern):
                if file.is_file() and not any(excluded in str(file) for excluded in self.EXCLUDED_DIRS):
                    test_files.append({
                        "path": str(file.relative_to(self.repo_path)),
                        "type": "test",
                    })
        
        return test_files

    def _extract_dependency_info(self) -> dict[str, Any]:
        """Extract dependency information."""
        deps = {
            "package_manager": None,
            "dependencies": [],
            "dev_dependencies": [],
        }
        
        # Check package.json
        package_json = self.repo_path / "package.json"
        if package_json.exists():
            import json
            with open(package_json) as f:
                data = json.load(f)
                deps["package_manager"] = "npm"
                deps["dependencies"] = list(data.get("dependencies", {}).keys())
                deps["dev_dependencies"] = list(data.get("devDependencies", {}).keys())
        
        # Check requirements.txt
        requirements_txt = self.repo_path / "requirements.txt"
        if requirements_txt.exists():
            deps["package_manager"] = "pip"
            deps["dependencies"] = [
                line.strip().split("==")[0].split(">=")[0].split("<=")[0]
                for line in requirements_txt.read_text().split("\n")
                if line.strip() and not line.startswith("#")
            ]
        
        # Check pyproject.toml
        pyproject_toml = self.repo_path / "pyproject.toml"
        if pyproject_toml.exists():
            deps["package_manager"] = "uv"
            # Simple extraction of dependencies
            content = pyproject_toml.read_text()
            import re
            dep_pattern = r'dependencies\s*=\s*\[(.*?)\]'
            match = re.search(dep_pattern, content, re.DOTALL)
            if match:
                deps_str = match.group(1)
                deps["dependencies"] = [
                    dep.strip().strip('"').strip("'").split(">=")[0].split("==")[0]
                    for dep in deps_str.split(",") if dep.strip()
                ]
        
        return deps

    def _identify_call_paths(self) -> list[dict[str, Any]]:
        """Identify major call paths in the codebase."""
        # This is a simplified version - in production, you'd use AST parsing
        call_paths = []
        
        # Look for common patterns
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                if not file.endswith((".py", ".js", ".ts", ".tsx")):
                    continue
                
                file_path = Path(root) / file
                try:
                    content = file_path.read_text(errors="ignore")
                    
                    # Look for main function or entrypoint
                    if "def main(" in content or "async def main(" in content:
                        call_paths.append({
                            "entrypoint": str(file_path.relative_to(self.repo_path)),
                            "type": "main_function",
                        })
                    
                    # Look for route definitions
                    if "@app.route" in content or "@router" in content or "app.get" in content:
                        call_paths.append({
                            "entrypoint": str(file_path.relative_to(self.repo_path)),
                            "type": "api_route",
                        })
                    
                except Exception:
                    continue
        
        return call_paths

    def _get_excluded_files_with_reasons(self) -> list[dict[str, str]]:
        """Get list of excluded files with reasons."""
        excluded = []
        
        for root, dirs, files in os.walk(self.repo_path):
            dirs[:] = [d for d in dirs if d not in self.EXCLUDED_DIRS]
            
            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(self.repo_path)
                
                if file in self.EXCLUDED_FILES:
                    excluded.append({
                        "path": str(rel_path),
                        "reason": "excluded_file_pattern",
                    })
                elif file_path.suffix.lower() not in self.CODE_EXTENSIONS:
                    excluded.append({
                        "path": str(rel_path),
                        "reason": "non_code_file",
                    })
        
        return excluded


# Singleton instance
repository_analyzer = RepositoryAnalyzer()
