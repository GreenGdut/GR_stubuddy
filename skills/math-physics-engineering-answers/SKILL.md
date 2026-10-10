---
name: math-physics-engineering-answers
description: 解答数学、物理、工学题目并将答案以文件交付。当需要求解数学/物理/工程问题、收到题目图片（input_*.png / input_*.jpg）、或 Stubuddy 要求生成 .tex/.svg 交付物时使用。Answer math, physics, and engineering problems from an input image and deliver the solution as a LaTeX (.tex) file plus optional SVG figures into the current Stubuddy project.
---

# Output Specification for Math, Physics, and Engineering Answers

## 1. Scope and priority

This specification governs model-generated answers to mathematics, physics, and engineering problems. The answer is delivered as files through an API; there is no chat window reserved for explanatory text. The final response payload MUST consist only of the required answer file(s).

The input is normally an image containing problem text, formulas, function plots, circuit diagrams, or other visual information. The upstream system guarantees that input filenames conform to the naming convention in Section 2. Do not add defensive filename validation or rename inputs.

## 2. Output directory and filenames

### Runtime output directory

Before processing the input, read the Stubuddy agent context from `~/.stubuddy/agent-context.json`, where `~` is the current user's home directory. The Stubuddy application creates and updates this file automatically. Its schema is:

```json
{
  "schemaVersion": 1,
  "targetFolder": "<absolute path>/Target_Stubuddy",
  "currentProject": "<absolute path>/Target_Stubuddy/ProjectNNN",
  "updatedAt": "<ISO 8601 timestamp>"
}
```

Use the non-null `currentProject` value as `CURRENT_PROJECT_DIR`. It is the absolute path to the numerically highest project directory known to the application under the user-selected `Target_Stubuddy` directory:

```text
<absolute path>/Target_Stubuddy/ProjectNNN
```

Here `ProjectNNN` matches `^Project[0-9]{3}$`; the application determines the highest project by comparing the three-digit sequence numerically. The model MUST NOT search the filesystem for `Target_Stubuddy`, infer its location from the repository, read any other application configuration to locate it, or select a different project directory.

If the context file is missing or unreadable, `schemaVersion` is unsupported, `currentProject` is null, or the referenced directory does not exist, stop without creating deliverables. Do not fall back to filesystem-wide discovery.

Write every generated `.tex` and `.svg` file directly into `CURRENT_PROJECT_DIR`. Do not create an additional output subdirectory. Paths outside `CURRENT_PROJECT_DIR` are not deliverables.

### Input and output filenames

Preserve the input file's complete basename (filename without its extension) exactly. Do not replace the `input_` prefix with `output_`.

For example:

- `input_001.png` → `input_001.tex`
- `input_001.png` → `input_001_1.svg`, `input_001_2.svg` when two figures are needed

Produce exactly one `.tex` file. Produce zero or more `.svg` files as required by the problem. Number SVGs consecutively from `_1` in the order they are referenced conceptually in the solution. Do not create empty or placeholder SVGs.

### Filename patterns

The input basename is `input_` followed by one or more underscore-separated alphanumeric components; the final component is the sequence identifier. Preserve the sequence text, including leading zeroes.

```regex
^input_(?:[A-Za-z0-9]+_)*[0-9]+$
```

Allowed input extensions are `.png` and `.jpg` (case-sensitive). Given the captured basename `B`, the required output patterns are:

```regex
^B\.tex$
^B_[1-9][0-9]*\.svg$
```

Here `B` is the literal input basename, regex-escaped before substitution. The SVG suffix is a positive integer without leading zeroes.

## 3. Read and analyze the input

1. Extract and transcribe the textual content, mathematical notation, labels, units, and stated conditions from the image.
2. Analyze the visual information—such as a graph, geometry, or circuit—and combine it with the extracted text before solving.
3. Solve the problem and verify that the result is consistent with the given conditions and units.

Do not omit relevant visual information or treat text extraction as a substitute for analyzing the image.

## 4. Answer content and style

- Write the answer in Chinese, using mathematical notation where appropriate.
- The `.tex` source is the sole textual answer. Write all answer text and mathematics in LaTeX; use XeLaTeX with `ctex` for Chinese typesetting.
- Be concise. Include only the necessary conclusion and essential reasoning or derivation. Unnecessary explanation, conversational filler, and unrequested commentary MUST be omitted.
- Do not expose internal reasoning, uncertainty monologue, self-correction, or drafting notes.
- Do not add generic openings such as "解：此题答案为：" or closing remarks such as "我给你答案，你直接复制即可。" Begin directly with the answer.

## 5. Figures and tables

- Generate function plots and tables as SVG using Python's `matplotlib`.
- Generate electrical circuit-analysis diagrams as SVG using Python's `SchemDraw` library.
- SVGs are independent deliverables for a downstream handwriting model. They are not embedded in, cited by, or referenced with file paths from the `.tex` file.
- In the `.tex` body, the only permitted textual mention of an image is the exact Chinese phrase `如图`. Do not describe the image in any other way.
- Do not include image embedding or reference syntax in the `.tex` file, including `\includegraphics`, `\includesvg`, `\input`, `\ref`, captions, or figure environments. The phrase `如图` does not authorize or imply an image reference command.
- Do not mention output paths, project directories, generated-file locations, or offer to convert or reorganize the images.
- If no plot, table, or circuit diagram is needed, return no SVG file.

## 6. Machine-readable contract

The following JSON describes the deliverable contract. It is specification metadata, not an additional output file.

```json
{
  "scope": "math_physics_engineering_answers",
  "delivery": "files_only",
  "input": {
    "extensions": [".png", ".jpg"],
    "basename_pattern": "^input_(?:[A-Za-z0-9]+_)*[0-9]+$",
    "filename_validation": "upstream_guaranteed"
  },
  "output_directory": {
    "context_manifest": "~/.stubuddy/agent-context.json",
    "context_schema_version": 1,
    "context_field": "currentProject",
    "runtime_name": "CURRENT_PROJECT_DIR",
    "path_shape": "<absolute path>/Target_Stubuddy/ProjectNNN",
    "project_basename_pattern": "^Project[0-9]{3}$",
    "selection": "numerically_highest_existing_project",
    "resolved_by": "Stubuddy_application",
    "filesystem_search_by_model": false,
    "write_files_directly_into_directory": true
  },
  "outputs": {
    "tex_count": 1,
    "tex_filename": "<input_basename>.tex",
    "tex_language": "Chinese",
    "tex_typesetting": "LaTeX with XeLaTeX and ctex",
    "svg_count": "zero_or_more_as_needed",
    "svg_filename": "<input_basename>_<positive_ordinal>.svg",
    "svg_format": "SVG",
    "svg_is_embedded_or_referenced_in_tex": false
  },
  "rendering": {
    "function_plots": "matplotlib",
    "tables": "matplotlib",
    "electrical_circuit_diagrams": "SchemDraw"
  },
  "image_mention_in_tex": {
    "only_allowed_phrase": "如图",
    "embedding_syntax_allowed": false,
    "captions_or_paths_allowed": false
  },
  "style": {
    "concise": true,
    "internal_reasoning_allowed": false,
    "conversational_filler_allowed": false
  }
}
```

## 7. Final validation

Before returning the files, confirm that:

1. `CURRENT_PROJECT_DIR` came from the `currentProject` field in `~/.stubuddy/agent-context.json`, and every deliverable was written directly into it with no output written elsewhere.
2. There is exactly one `.tex` file, named from the input basename.
3. Each necessary SVG is a separate file, uses the required basename and consecutive numbering, and was generated with the required library for its content type.
4. The `.tex` answer is concise Chinese LaTeX and contains no image embedding syntax, file paths, captions, or image descriptions beyond `如图`.
5. No chat prose, internal reasoning, placeholder figure, PDF, or unrequested auxiliary file is included.
