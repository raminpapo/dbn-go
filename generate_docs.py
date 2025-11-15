#!/usr/bin/env python3
"""
Repository Documentation Generator
Generates comprehensive documentation for the dbn-go repository.
"""

import os
import json
import hashlib
import re
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import subprocess

# Configuration
REPO_ROOT = Path("/home/user/dbn-go")
DOCS_ROOT = REPO_ROOT / "docs"
PROGRESS_LOG = DOCS_ROOT / ".progress.log"
MANIFEST_FILE = DOCS_ROOT / "manifest.json"

# Binary file extensions to skip
BINARY_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.dbn', '.zst',
    '.bin', '.exe', '.dll', '.so', '.dylib', '.a', '.o', '.wasm'
}

# Text file extensions to process
TEXT_EXTENSIONS = {
    '.go', '.md', '.txt', '.yaml', '.yml', '.json', '.toml',
    '.mod', '.sum', '.py', '.sh', '.Dockerfile'
}

class DocGenerator:
    def __init__(self):
        self.manifest = self.load_manifest()
        self.file_keywords = defaultdict(list)
        self.all_files = []
        self.docs_created = 0
        self.bytes_written = 0
        self.errors = []

    def load_manifest(self):
        """Load existing manifest or create new one"""
        if MANIFEST_FILE.exists():
            with open(MANIFEST_FILE, 'r') as f:
                return json.load(f)
        return {
            "repo_name": "dbn-go",
            "repo_source": str(REPO_ROOT),
            "commit_sha": self.get_commit_sha(),
            "generator_version": "1.0.0",
            "timestamp_start": datetime.utcnow().isoformat() + "Z",
            "file_count": 0,
            "docs_count": 0,
            "bytes_written": 0,
            "status": "in_progress",
            "files_scanned": [],
            "checksums": {}
        }

    def get_commit_sha(self):
        """Get current git commit SHA"""
        try:
            result = subprocess.run(
                ['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD'],
                capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except:
            return "unknown"

    def scan_repository(self):
        """Scan repository and classify files"""
        for root, dirs, files in os.walk(REPO_ROOT):
            # Skip .git and docs directories
            dirs[:] = [d for d in dirs if d not in {'.git', 'docs'}]

            for file in files:
                file_path = Path(root) / file
                rel_path = file_path.relative_to(REPO_ROOT)

                file_info = {
                    "path": str(rel_path),
                    "size": file_path.stat().st_size,
                    "extension": file_path.suffix,
                    "is_binary": self.is_binary_file(file_path)
                }
                self.all_files.append(file_info)

        self.manifest["file_count"] = len(self.all_files)
        return self.all_files

    def is_binary_file(self, file_path):
        """Determine if file is binary"""
        ext = file_path.suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return True
        if ext in TEXT_EXTENSIONS or file_path.name in {'Makefile', 'Dockerfile', '.gitignore', '.dockerignore'}:
            return False

        # Try reading first 8192 bytes
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)
                return b'\x00' in chunk
        except:
            return True

    def extract_keywords_from_go(self, content, file_path):
        """Extract keywords from Go source file"""
        keywords = {}

        # Extract package name
        package_match = re.search(r'package\s+(\w+)', content)
        if package_match:
            keywords[package_match.group(1)] = f"Package name - {file_path}"

        # Extract type definitions
        for match in re.finditer(r'type\s+(\w+)\s+', content):
            name = match.group(1)
            keywords[name] = f"Type definition in {file_path}"

        # Extract function names
        for match in re.finditer(r'func\s+(?:\(.*?\)\s+)?(\w+)', content):
            name = match.group(1)
            keywords[name] = f"Function in {file_path}"

        # Extract const/var
        for match in re.finditer(r'(?:const|var)\s+(\w+)', content):
            name = match.group(1)
            keywords[name] = f"Constant/Variable in {file_path}"

        return keywords

    def generate_file_docs(self, file_info):
        """Generate _docs.md for a single file"""
        file_path = REPO_ROOT / file_info["path"]
        rel_path = file_info["path"]

        # Create corresponding docs directory
        docs_dir = DOCS_ROOT / Path(rel_path).parent
        docs_dir.mkdir(parents=True, exist_ok=True)

        filename_base = Path(rel_path).stem
        filename_ext = Path(rel_path).suffix
        safe_name = filename_base.replace('.', '_')

        docs_file = docs_dir / f"{safe_name}{filename_ext}_docs.md"
        kw_file = docs_dir / f"{safe_name}{filename_ext}_kw.md"

        # Handle binary files
        if file_info["is_binary"]:
            content = self.generate_binary_file_docs(file_info)
            self.write_file(docs_file, content)
            self.docs_created += 1
            return

        # Read text file
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                file_content = f.read()
        except Exception as e:
            self.errors.append(f"Failed to read {rel_path}: {e}")
            return

        # Generate docs
        docs_content = self.generate_text_file_docs(file_info, file_content)
        kw_content = self.generate_keywords_docs(file_info, file_content)

        self.write_file(docs_file, docs_content)
        self.write_file(kw_file, kw_content)
        self.docs_created += 2

    def generate_binary_file_docs(self, file_info):
        """Generate documentation for binary files"""
        return f"""# {file_info['path']} - Binary File Documentation

## File Metadata
- **Path**: `{file_info['path']}`
- **Type**: Binary file
- **Size**: {file_info['size']} bytes
- **Extension**: {file_info['extension']}

## Description
This is a binary file and cannot be transcribed as text.

## Handling
To work with this file:
- For images: Use image viewer or processing tools
- For compressed files (.zst): Use zstd decompression
- For .dbn files: Use the dbn-go library to read and process

## Related Files
- See the parent directory index for related documentation
"""

    def generate_text_file_docs(self, file_info, content):
        """Generate comprehensive documentation for text files"""
        rel_path = file_info['path']
        lines = content.split('\n')

        # Extract keywords based on file type
        if rel_path.endswith('.go'):
            keywords = self.extract_keywords_from_go(content, rel_path)
            self.file_keywords[rel_path] = keywords

        doc = f"""# {rel_path} - Documentation

## File Metadata
- **Path**: `{rel_path}`
- **Size**: {file_info['size']} bytes ({len(lines)} lines)
- **Extension**: {file_info['extension']}
- **Type**: Text file

## Original Source

```{self.get_code_fence_lang(file_info['extension'])}
{content}
```

## High-Level Overview

"""

        # Add file-type specific overview
        if rel_path.endswith('.go'):
            doc += self.generate_go_overview(content)
        elif rel_path.endswith('.md'):
            doc += "This is a Markdown documentation file.\n\n"
        elif rel_path.endswith(('.yaml', '.yml')):
            doc += "This is a YAML configuration file.\n\n"
        elif rel_path.endswith('.json'):
            doc += "This is a JSON data/configuration file.\n\n"
        elif rel_path.endswith('.toml'):
            doc += "This is a TOML configuration file.\n\n"
        elif rel_path.endswith('.mod'):
            doc += "This is a Go module definition file.\n\n"
        else:
            doc += f"This is a {file_info['extension']} file.\n\n"

        doc += """## Detailed Walkthrough

"""

        # Add detailed analysis for Go files
        if rel_path.endswith('.go'):
            doc += self.generate_go_walkthrough(content)

        doc += f"""
## Usage Examples

See the repository README and related test files for usage examples.

## Related Files

- Parent directory: `{Path(rel_path).parent}/`
- See folder index for related files

## Testing

"""

        if rel_path.endswith('.go') and not rel_path.endswith('_test.go'):
            test_file = rel_path.replace('.go', '_test.go')
            doc += f"- Test file: `{test_file}`\n"
            doc += "- Run tests: `go test`\n"

        doc += """
---
*Generated by repo-book-generator*
"""

        return doc

    def get_code_fence_lang(self, ext):
        """Get code fence language identifier"""
        lang_map = {
            '.go': 'go',
            '.py': 'python',
            '.sh': 'bash',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.toml': 'toml',
            '.md': 'markdown',
            '.txt': 'text'
        }
        return lang_map.get(ext, 'text')

    def generate_go_overview(self, content):
        """Generate overview for Go files"""
        overview = []

        # Find package
        package_match = re.search(r'package\s+(\w+)', content)
        if package_match:
            overview.append(f"**Package**: `{package_match.group(1)}`\n")

        # Count types, functions, etc.
        types = len(re.findall(r'\ntype\s+\w+', content))
        funcs = len(re.findall(r'\nfunc\s+', content))
        consts = len(re.findall(r'\nconst\s+', content))
        vars = len(re.findall(r'\nvar\s+', content))

        overview.append(f"This Go source file contains:\n")
        overview.append(f"- {types} type definitions\n")
        overview.append(f"- {funcs} functions/methods\n")
        overview.append(f"- {consts} constant blocks\n")
        overview.append(f"- {vars} variable blocks\n")

        return ''.join(overview) + '\n'

    def generate_go_walkthrough(self, content):
        """Generate detailed walkthrough for Go files"""
        walkthrough = []

        # Extract and document major components
        walkthrough.append("### Types and Structures\n\n")

        for match in re.finditer(r'type\s+(\w+)\s+(struct|interface|[\w\[\]]+)', content, re.MULTILINE):
            name, kind = match.groups()
            walkthrough.append(f"- **{name}**: {kind}\n")

        walkthrough.append("\n### Functions and Methods\n\n")

        for match in re.finditer(r'func\s+(?:\([^)]+\)\s+)?(\w+)', content):
            name = match.group(1)
            walkthrough.append(f"- `{name}()`\n")

        return ''.join(walkthrough)

    def generate_keywords_docs(self, file_info, content):
        """Generate keyword index for file"""
        rel_path = file_info['path']

        kw_doc = f"""# {rel_path} - Keyword Index

## Keywords and Identifiers

"""

        # Get keywords based on file type
        keywords = {}
        if rel_path.endswith('.go'):
            keywords = self.extract_keywords_from_go(content, rel_path)

        if keywords:
            # Sort keywords alphabetically
            for kw in sorted(keywords.keys()):
                desc = keywords[kw]
                kw_doc += f"### {kw}\n\n"
                kw_doc += f"- **Description**: {desc}\n"
                kw_doc += f"- **File**: `{rel_path}`\n\n"
        else:
            kw_doc += "*No keywords extracted for this file type.*\n"

        kw_doc += """
---
*Generated by repo-book-generator*
"""

        return kw_doc

    def write_file(self, path, content):
        """Write file and track bytes"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        self.bytes_written += len(content.encode('utf-8'))

        # Calculate checksum
        checksum = hashlib.sha256(content.encode('utf-8')).hexdigest()
        self.manifest["checksums"][str(path.relative_to(DOCS_ROOT))] = checksum

    def generate_folder_docs(self):
        """Generate index.md, doc.md, sub.md for each folder"""
        folders = set()
        for file_info in self.all_files:
            path = Path(file_info['path'])
            # Add all parent directories
            for parent in path.parents:
                if str(parent) != '.':
                    folders.add(str(parent))

        folders.add('')  # Root

        for folder in sorted(folders):
            self.generate_folder_index(folder)
            self.generate_folder_doc(folder)
            self.generate_folder_sub(folder)

    def generate_folder_index(self, folder):
        """Generate index.md for a folder"""
        docs_dir = DOCS_ROOT / folder
        docs_dir.mkdir(parents=True, exist_ok=True)
        index_file = docs_dir / "index.md"

        # Find direct children
        children_files = []
        children_dirs = set()

        for file_info in self.all_files:
            file_path = Path(file_info['path'])
            if folder == '':
                parent = str(file_path.parent) if file_path.parent != Path('.') else ''
            else:
                parent = str(file_path.parent)

            if parent == folder:
                children_files.append(file_info)
            elif parent.startswith(folder + '/'):
                # Direct subdirectory
                subdir = parent[len(folder)+1:].split('/')[0] if folder else parent.split('/')[0]
                children_dirs.add(subdir)

        content = f"""# {'Root' if folder == '' else folder} - Directory Index

## Overview

This directory contains {len(children_files)} files and {len(children_dirs)} subdirectories.

## Subdirectories

"""

        for subdir in sorted(children_dirs):
            rel_subdir = f"{folder}/{subdir}" if folder else subdir
            content += f"- [`{subdir}/`](./{subdir}/index.md)\n"

        content += "\n## Files\n\n"

        for file_info in sorted(children_files, key=lambda x: x['path']):
            filename = Path(file_info['path']).name
            safe_name = Path(file_info['path']).stem.replace('.', '_')
            ext = Path(file_info['path']).suffix
            docs_link = f"{safe_name}{ext}_docs.md"
            content += f"- [`{filename}`](./{docs_link}) - {file_info['size']} bytes\n"

        content += """
## Documentation

- [Detailed Documentation](./doc.md)
- [Keywords Index](./sub.md)

---
*Generated by repo-book-generator*
"""

        self.write_file(index_file, content)
        self.docs_created += 1

    def generate_folder_doc(self, folder):
        """Generate doc.md narrative for folder"""
        docs_dir = DOCS_ROOT / folder
        doc_file = docs_dir / "doc.md"

        display_name = folder if folder else "Root"

        content = f"""# {display_name} - Documentation

## Purpose

"""

        # Add specific documentation based on folder
        if folder == '':
            content += """This is the root directory of the dbn-go repository. It contains the core Go package implementation of Databento Binary Encoding (DBN) format support.

### Main Components

- **Core Types**: `structs.go`, `consts.go` - Define DBN message types and constants
- **Parsers**: `dbn_scanner.go`, `json_scanner.go` - File reading and parsing
- **Metadata**: `metadata.go` - DBN file metadata handling
- **Visitors**: `visitor.go` - Pattern for processing DBN records

"""
        elif folder == 'cmd':
            content += """This directory contains command-line tools and applications built on top of the dbn-go library.

"""
        elif folder == 'hist':
            content += """This directory contains the implementation of Databento's Historical API client.

"""
        elif folder == 'live':
            content += """This directory contains the implementation of Databento's Live API client for real-time market data streaming.

"""
        elif folder == 'internal':
            content += """This directory contains internal packages not meant for external use.

"""
        else:
            content += f"""This directory is part of the {display_name} module/component.

"""

        content += """
## Architecture

See the individual file documentation for detailed technical information.

---
*Generated by repo-book-generator*
"""

        self.write_file(doc_file, content)
        self.docs_created += 1

    def generate_folder_sub(self, folder):
        """Generate sub.md keyword aggregation for folder"""
        docs_dir = DOCS_ROOT / folder
        sub_file = docs_dir / "sub.md"

        display_name = folder if folder else "Root"

        content = f"""# {display_name} - Aggregated Keywords

## Keywords from this directory and subdirectories

"""

        # Aggregate keywords from all files in this folder and subfolders
        folder_keywords = defaultdict(list)
        for file_path, keywords in self.file_keywords.items():
            if folder == '' or file_path.startswith(folder + '/'):
                for kw, desc in keywords.items():
                    folder_keywords[kw].append((desc, file_path))

        if folder_keywords:
            for kw in sorted(folder_keywords.keys()):
                content += f"### {kw}\n\n"
                for desc, file_path in folder_keywords[kw]:
                    content += f"- {desc} - [`{file_path}`](../{file_path})\n"
                content += "\n"
        else:
            content += "*No keywords found in this directory.*\n"

        content += """
---
*Generated by repo-book-generator*
"""

        self.write_file(sub_file, content)
        self.docs_created += 1

    def save_manifest(self):
        """Save manifest file"""
        self.manifest["docs_count"] = self.docs_created
        self.manifest["bytes_written"] = self.bytes_written
        self.manifest["timestamp_end"] = datetime.utcnow().isoformat() + "Z"
        self.manifest["status"] = "completed" if not self.errors else "completed_with_errors"
        self.manifest["error_count"] = len(self.errors)

        with open(MANIFEST_FILE, 'w') as f:
            json.dump(self.manifest, f, indent=2)

    def run(self):
        """Main execution"""
        print("Starting documentation generation...")

        print("1. Scanning repository...")
        self.scan_repository()
        print(f"   Found {len(self.all_files)} files")

        print("2. Generating per-file documentation...")
        for i, file_info in enumerate(self.all_files):
            if (i + 1) % 10 == 0:
                print(f"   Processed {i + 1}/{len(self.all_files)} files...")
            self.generate_file_docs(file_info)

        print("3. Generating folder documentation...")
        self.generate_folder_docs()

        print("4. Saving manifest...")
        self.save_manifest()

        print(f"\nCompleted!")
        print(f"- Files scanned: {len(self.all_files)}")
        print(f"- Docs created: {self.docs_created}")
        print(f"- Bytes written: {self.bytes_written}")
        print(f"- Errors: {len(self.errors)}")

        return {
            "files_scanned": len(self.all_files),
            "docs_created": self.docs_created,
            "bytes_written": self.bytes_written,
            "errors": self.errors
        }

if __name__ == "__main__":
    generator = DocGenerator()
    result = generator.run()

    if result["errors"]:
        print("\nErrors encountered:")
        for error in result["errors"]:
            print(f"  - {error}")
