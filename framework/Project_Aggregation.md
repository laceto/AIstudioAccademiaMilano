# Project Aggregation Framework

This document outlines the process and framework for creating and managing multiple repositories (projects) while allowing aggregation of outputs to create higher-level AI products.

---

## Workflow Overview

### 1. **User Input → New Project Repository**
- Each time the system receives a new request for an AI product:
  1. **Create a new GitHub repository** for the product using the naming convention `AIstudio_Project_<timestamp>`.
  2. Add boilerplate files to the repository:
     - README.md (Project description and usage instructions)
     - Template structure for code and dependencies.
  3. Link this repository to the central `ProjectRegistry.md`.

### 2. **Central Repository as Management Hub**
The `AIstudioAccademiaMilano` repository serves as the **management hub**, tracking and linking all individual project repositories.

#### **Registry of Projects**
- Maintain a `ProjectRegistry.md` file under the `framework/` folder:
  - Includes metadata such as repository name, description, and purpose.
  - Example entry:
    ```markdown
    ## AIStudio Projects
    
    - [AIstudio_Project_WeatherApp](https://github.com/laceto/AIstudio_Project_WeatherApp):
      A weather app that leverages AI to showcase real-time and forecasted weather patterns dynamically.
    - [AIstudio_Project_TextSummarizer](https://github.com/laceto/AIstudio_Project_TextSummarizer):
      Simplifies text analysis by summarizing long information into concise representations.
    ```

#### **Aggregate Outputs for Meta-Products**
- Gather outputs from 10+ repositories to create high-level or aggregated products.
- Meta-products combine features and functionalities of individual projects to solve complex user problems.

---

## Roles and Responsibilities

### For Individual Repositories:
- **Creation**:
  - New GitHub repositories are auto-created per user request.
  - Include default templates and workflows (e.g., LangChain setup, FastAPI).
- **Maintenance**:
  - Each repository should follow best practices for README files, modular code, and CI/CD pipelines.

### For `AIstudioAccademiaMilano` Repository:
- **Submodules for Project Repos**:
  - Link individual repositories as Git submodules for better central management.
  - Track submodules for updates and changes.
- **Aggregation Scripts**:
  - Set up scripts to clone, pull, and use outputs from all linked submodules.

---

## Technical Implementation

### **Git Workflow for Projects**
1. **Add New Submodule:**
   ```bash
   git submodule add https://github.com/laceto/AIstudio_Project_<project_name>.git projects/<project_name>
   git commit -m "Added new project as submodule: <project_name>"
   ```

2. **Update All Submodules:**
   ```bash
   git submodule update --init --recursive
   ```

3. **Remove a Submodule:**
   ```bash
   git submodule deinit -f projects/<project_name>
   git rm -f projects/<project_name>
   ```

---

### **Automation for Repository Creation**
- Use GitHub APIs to:
  - Create repositories dynamically with boilerplate files.
  - Programmatically link/update the `ProjectRegistry.md` file.

#### **Example Python Script**:
Here’s a script idea to create a new repository:
```python
import requests

def create_repo(repo_name):
    url = "https://api.github.com/user/repos"
    headers = {"Authorization": "token <your_personal_access_token>"}
    payload = {"name": repo_name, "private": False}

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        print(f"Repository {repo_name} created at {response.json()['html_url']}")
    else:
        print(f"Failed to create repository: {response.json()}")

create_repo("AIstudio_Project_ExampleProduct")
```

---

## Expansion Philosophy
- Promote the creation of diverse AI projects to increase the likelihood of success.
- Advertise publicly hosted repos and invite developers/contributors to collaborate.
- Leverage meta-products to attract investments or partnerships.

---

Any new ideas or revisions can be directly reflected in this framework to adapt to evolving requirements.