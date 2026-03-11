# CERN GitLab Benchmark: Questions and Answers

This document contains 10 benchmark questions designed to test model performance when using either:
- **Model + cerngitlab-cli** (command-line interface)
- **Model + cerngitlab MCP** (Model Context Protocol server)

Each question tests different capabilities of the CERN GitLab tools, focusing on **stable information** that won't change frequently (project structure, configurations, historical facts).

---

## Question 1: Project Discovery

**Question:** Find the LHCb DaVinci project. What is its project ID, namespace path, and default branch?

**Expected Answer:**
- Project ID: 544
- Path: lhcb/DaVinci
- Default Branch: master
- URL: https://gitlab.cern.ch/lhcb/DaVinci

**Tools Used:** `search-projects` or `get-project-info`
**Difficulty:** Easy
**Category:** Project Discovery
**Stability:** High - Project ID and path never change

---

## Question 2: Framework Relationships

**Question:** Which LHCb project is built on top of the Gaudi framework and contains general purpose classes used throughout LHCb software? What is its project ID?

**Expected Answer:**
- Project: lhcb/LHCb
- Project ID: 399
- Description: The LHCb project contains general purpose classes used throughout the LHCb software. It is built on top of the Gaudi framework.
- Documentation: http://cern.ch/lhcbdoc/lhcb

**Tools Used:** `search-projects` with query "Gaudi" or "LHCb"
**Difficulty:** Easy
**Category:** Project Discovery
**Stability:** High - Core project relationships don't change

---

## Question 3: Build System Detection

**Question:** What build system does the DaVinci project use? What is the minimum required version?

**Expected Answer:**
- Build System: CMake
- Minimum Version: 3.15
- Evidence: CMakeLists.txt contains `cmake_minimum_required(VERSION 3.15)`

**Tools Used:** `get-file` (CMakeLists.txt) or `inspect-project`
**Difficulty:** Easy
**Category:** Build Configuration
**Stability:** High - Build system choices are long-term decisions

---

## Question 4: Project Subdirectories

**Question:** According to DaVinci's CMakeLists.txt, which subdirectories are registered in the build configuration?

**Expected Answer:**
Subdirectories (from `lhcb_add_subdirectories`):
1. DaVinciExamples
2. DaVinciTutorials
3. DaVinciSys
4. DaVinciTests
5. Phys/DaVinci
6. Phys/FunTuple
7. HltEfficiencyChecker
8. DaVinciCache

**Tools Used:** `get-file` (CMakeLists.txt)
**Difficulty:** Medium
**Category:** Project Structure
**Stability:** High - Core subdirectories rarely change

---

## Question 5: CI/CD Pipeline Structure

**Question:** What are the CI/CD stages defined in DaVinci's `.gitlab-ci.yml` file?

**Expected Answer:**
- Stages: test, build, docs, deploy
- Jobs include: python-linting, build, build-docs, pages
- Uses CVMFS tags for execution
- Based on alma9-devel container image

**Tools Used:** `get-file` (.gitlab-ci.yml) or `inspect-project`
**Difficulty:** Medium
**Category:** CI/CD Configuration
**Stability:** High - CI stage structure is stable

---

## Question 6: License Information

**Question:** What license is used by the DaVinci project? Where is this stated in the project files?

**Expected Answer:**
- License: GNU General Public Licence version 3 (GPL Version 3)
- Stated in: CMakeLists.txt and .gitlab-ci.yml headers
- Reference: copied verbatim in the file "COPYING"
- Copyright: CERN for the benefit of the LHCb Collaboration

**Tools Used:** `get-file` (CMakeLists.txt or .gitlab-ci.yml)
**Difficulty:** Medium
**Category:** Legal/Compliance
**Stability:** Very High - License rarely changes

---

## Question 7: CMake Module Configuration

**Question:** What file is in the `cmake/` directory of the DaVinci project, and what does it suggest about the project's dependency management?

**Expected Answer:**
- File: DaVinciDependencies.cmake
- Path: cmake/DaVinciDependencies.cmake
- Suggests: Modular dependency management using CMake's include mechanism
- The main CMakeLists.txt includes it via `include(DaVinciDependencies)`

**Tools Used:** `list-files` (cmake directory) + `get-file`
**Difficulty:** Medium
**Category:** Project Structure
**Stability:** High - CMake structure is stable

---

## Question 8: Project Ecosystem Analysis

**Question:** What programming ecosystems does the DaVinci project support according to project inspection?

**Expected Answer:**
- Ecosystems: C++, Fortran
- Build Systems: CMake
- Primary Language: C++ (evident from project structure)

**Tools Used:** `inspect-project`
**Difficulty:** Easy
**Category:** Project Analysis
**Stability:** High - Core language choices are stable

---

## Question 9: Connection and Authentication

**Question:** Test the connection to CERN GitLab. Report the GitLab URL, authentication status, and whether public access is available.

**Expected Answer (without token):**
```json
{
  "status": "connected",
  "gitlab_url": "https://gitlab.cern.ch",
  "authenticated": false,
  "public_access": true,
  "note": "No token provided — public access only"
}
```

**Tools Used:** `test-connection`
**Difficulty:** Easy
**Category:** Configuration
**Stability:** Very High - Infrastructure details don't change

---

## Question 10: Multi-Step Project Research

**Question:** I'm researching the Gaudi framework. Find the main Gaudi project, tell me its project ID, what it's used for, and whether it's experiment-specific or general-purpose.

**Expected Answer:**
- Project: gaudi/Gaudi
- Project ID: 38
- Purpose: An open project for providing interfaces and services for building HEP experiment frameworks
- Scope: **Experiment independent** - used for event data processing applications across multiple experiments
- URL: https://gitlab.cern.ch/gaudi/Gaudi
- Default Branch: master

**Tools Used:** `search-projects` → `get-project-info`
**Difficulty:** Medium
**Category:** Multi-Step Research
**Stability:** Very High - Gaudi's purpose and identity are fundamental

---

## Scoring Guide

| Score | Criteria |
|-------|----------|
| 5/5 | All facts correct, properly sourced from tool output |
| 4/5 | Minor details incorrect but core facts accurate |
| 3/5 | Major facts correct but missing key details |
| 2/5 | Some correct information but significant errors |
| 1/5 | Mostly incorrect or hallucinated information |
| 0/5 | No answer or completely wrong |

## Evaluation Metrics

When comparing **Model + CLI** vs **Model + MCP**, measure:

1. **Accuracy:** Are the facts correct? (Primary metric)
2. **Completeness:** Did it answer all parts of the question?
3. **Tool Selection:** Did it use the most efficient tools?
4. **Efficiency:** How many tool calls were needed?
5. **Hallucination Rate:** Did it invent any information?
6. **Source Attribution:** Did it reference where information came from?

## Why These Questions Are Stable

| Question | Why It's Stable |
|----------|-----------------|
| 1. Project ID/Path | GitLab project IDs are immutable |
| 2. Framework relationships | Core project purposes don't change |
| 3. Build system | CMake migration is a one-time decision |
| 4. Subdirectories | Core structure changes rarely |
| 5. CI stages | Pipeline structure is stable |
| 6. License | Legal licensing rarely changes |
| 7. CMake modules | Build configuration is stable |
| 8. Ecosystems | Language choices are long-term |
| 9. Connection | Infrastructure is constant |
| 10. Gaudi purpose | Fundamental project identity |

## Notes for Evaluators

- **Questions 1-3**: Basic discovery - both approaches should score 5/5
- **Questions 4-7**: File reading and analysis - tests tool precision
- **Questions 8-9**: Project inspection and configuration
- **Question 10**: Multi-step reasoning without requiring chained API calls

**Avoid hallucination traps:**
- Don't ask about star counts (change frequently)
- Don't ask about "latest" releases (changes with each release)
- Don't ask about open issue counts (changes daily)
- Don't ask about recent activity dates (changes constantly)

**Focus on:**
- Project IDs and paths (immutable)
- File contents (change infrequently)
- Configuration files (stable by nature)
- Project descriptions and purposes (rarely change)
- Build systems and structures (long-term decisions)
