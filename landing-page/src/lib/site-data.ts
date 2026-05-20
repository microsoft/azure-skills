import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import matter from "gray-matter";

const runtimeCwd = process.cwd();
const repositoryRoot = path.basename(runtimeCwd) === "landing-page" ? path.resolve(runtimeCwd, "..") : runtimeCwd;
const repository = "https://github.com/microsoft/azure-skills";

type SkillFrontmatter = {
  name?: string;
  description?: string;
  metadata?: {
    version?: string;
  };
};

type PluginManifest = {
  name?: string;
  version?: string;
  description?: string;
};

export type SkillCard = {
  name: string;
  slug: string;
  category: string;
  scenario: string;
  role: string;
  summary: string;
  description: string;
  version: string;
  prompt: string;
  highlights: string[];
  icon: string;
  href: string;
  order: number;
};

type SkillProfile = {
  category: string;
  scenario: string;
  role: string;
  summary: string;
  prompt: string;
  highlights: string[];
  icon: string;
  order: number;
};

export type InstallSurface = {
  id: string;
  name: string;
  shortName: string;
  detail: string;
  command: string;
  badge: string;
  status: string;
  language: string;
  title: string;
  icon: string;
  notes: string[];
};

export type Capability = {
  label: string;
  title: string;
  description: string;
  icon: string;
};

export type Workflow = {
  label: string;
  prompt: string;
  description: string;
  icon: string;
};

const skillProfiles: Record<string, SkillProfile> = {
  "azure-prepare": {
    category: "Build and deploy",
    scenario: "Prepare",
    role: "Deployment readiness",
    summary: "Plans Azure hosting, infrastructure, identity, and app configuration before deployment.",
    prompt: "Prepare this app for Azure.",
    highlights: ["Plan first", "Generate IaC", "Choose hosting"],
    icon: "lucide:clipboard-list",
    order: 1
  },
  "azure-validate": {
    category: "Build and deploy",
    scenario: "Validate",
    role: "Preflight checks",
    summary: "Checks Azure infrastructure and app configuration before changes are deployed.",
    prompt: "Validate my Azure deployment files.",
    highlights: ["Review IaC", "Check config", "Catch drift"],
    icon: "lucide:badge-check",
    order: 2
  },
  "azure-deploy": {
    category: "Build and deploy",
    scenario: "Deploy",
    role: "Release execution",
    summary: "Deploys applications and infrastructure with recovery steps for common Azure failures.",
    prompt: "Deploy this project to Azure.",
    highlights: ["Run azd", "Recover failures", "Verify release"],
    icon: "lucide:rocket",
    order: 3
  },
  "azure-upgrade": {
    category: "Build and deploy",
    scenario: "Evolve",
    role: "Modernization path",
    summary: "Guides Azure app upgrades while preserving deployment and operations guardrails.",
    prompt: "Upgrade this Azure app.",
    highlights: ["Modernize safely", "Preserve IaC", "Update runtime"],
    icon: "lucide:arrow-up-circle",
    order: 4
  },
  "azure-enterprise-infra-planner": {
    category: "Architecture",
    scenario: "Enterprise plan",
    role: "Landing-zone design",
    summary: "Creates enterprise-ready infrastructure plans across networking, identity, governance, and operations.",
    prompt: "Plan enterprise Azure infrastructure for this app.",
    highlights: ["Network topology", "Governance", "Platform standards"],
    icon: "lucide:building-2",
    order: 10
  },
  "azure-compute": {
    category: "Architecture",
    scenario: "Compute",
    role: "Service selection",
    summary: "Chooses the right Azure compute service for application shape, scale, and operations needs.",
    prompt: "What Azure compute should host this workload?",
    highlights: ["ACA", "App Service", "Functions"],
    icon: "lucide:cpu",
    order: 11
  },
  "azure-kubernetes": {
    category: "Architecture",
    scenario: "Kubernetes",
    role: "AKS guidance",
    summary: "Guides AKS architecture, deployment, operations, and troubleshooting workflows.",
    prompt: "Help me run this workload on AKS.",
    highlights: ["AKS", "Helm", "Cluster checks"],
    icon: "lucide:ship-wheel",
    order: 12
  },
  "airunway-aks-setup": {
    category: "Architecture",
    scenario: "AI Runway",
    role: "AKS platform setup",
    summary: "Sets up AI Runway patterns on AKS for platform teams and application developers.",
    prompt: "Set up AI Runway on AKS.",
    highlights: ["Platform setup", "AKS", "AI workloads"],
    icon: "lucide:plane",
    order: 13
  },
  "azure-reliability": {
    category: "Architecture",
    scenario: "Reliability",
    role: "Resilience review",
    summary: "Reviews architecture and operations choices against Azure reliability practices.",
    prompt: "Review this Azure architecture for reliability.",
    highlights: ["Resilience", "Availability", "Recovery"],
    icon: "lucide:heart-pulse",
    order: 14
  },
  "azure-cloud-migrate": {
    category: "Architecture",
    scenario: "Migration",
    role: "Cloud transition",
    summary: "Plans and executes application migration paths into Azure with service-fit guidance.",
    prompt: "Migrate this application to Azure.",
    highlights: ["Assess", "Map services", "Modernize"],
    icon: "lucide:cloud-upload",
    order: 15
  },
  "azure-cost": {
    category: "Governance",
    scenario: "Cost",
    role: "Optimization",
    summary: "Finds cost drivers and recommends Azure sizing, pricing, and cleanup improvements.",
    prompt: "Find cost savings across my Azure subscription.",
    highlights: ["Pricing", "Rightsize", "Clean up"],
    icon: "lucide:coins",
    order: 20
  },
  "azure-compliance": {
    category: "Governance",
    scenario: "Compliance",
    role: "Policy alignment",
    summary: "Helps align Azure resources and deployments with compliance and security expectations.",
    prompt: "Check this Azure deployment for compliance risks.",
    highlights: ["Policy", "Security", "Evidence"],
    icon: "lucide:scale",
    order: 21
  },
  "azure-rbac": {
    category: "Governance",
    scenario: "RBAC",
    role: "Access control",
    summary: "Selects least-privilege Azure roles for identities, apps, services, and operators.",
    prompt: "What role should this managed identity use?",
    highlights: ["Least privilege", "Role assignment", "Identity"],
    icon: "lucide:key-round",
    order: 22
  },
  "entra-app-registration": {
    category: "Governance",
    scenario: "App identity",
    role: "Entra registration",
    summary: "Creates and configures Entra app registrations for secure Azure integrations.",
    prompt: "Create an Entra app registration for this service.",
    highlights: ["App registration", "Secrets", "Permissions"],
    icon: "lucide:id-card",
    order: 23
  },
  "entra-agent-id": {
    category: "Governance",
    scenario: "Agent identity",
    role: "Identity setup",
    summary: "Configures Entra identity patterns for agents and service integrations.",
    prompt: "Set up an Entra identity for this agent.",
    highlights: ["Managed identity", "Agent access", "Permissions"],
    icon: "lucide:fingerprint",
    order: 24
  },
  "azure-diagnostics": {
    category: "Operate",
    scenario: "Diagnostics",
    role: "Troubleshooting",
    summary: "Uses Azure signals and tools to diagnose failing applications and infrastructure.",
    prompt: "Troubleshoot why my Azure app is failing.",
    highlights: ["Logs", "Metrics", "Root cause"],
    icon: "lucide:stethoscope",
    order: 30
  },
  "appinsights-instrumentation": {
    category: "Operate",
    scenario: "Observability",
    role: "Application Insights",
    summary: "Adds Application Insights instrumentation and telemetry patterns to applications.",
    prompt: "Add Application Insights to this app.",
    highlights: ["Telemetry", "Tracing", "App Insights"],
    icon: "lucide:activity",
    order: 31
  },
  "azure-resource-lookup": {
    category: "Operate",
    scenario: "Inventory",
    role: "Resource discovery",
    summary: "Finds and explains Azure resources, groups, subscriptions, and relationships.",
    prompt: "List my Azure resource groups.",
    highlights: ["Inventory", "Subscriptions", "Resource graph"],
    icon: "lucide:search",
    order: 32
  },
  "azure-resource-visualizer": {
    category: "Operate",
    scenario: "Visualize",
    role: "Architecture map",
    summary: "Creates diagrams and summaries from Azure resource relationships.",
    prompt: "Visualize my Azure resources.",
    highlights: ["Diagrams", "Dependencies", "Topology"],
    icon: "lucide:network",
    order: 33
  },
  "azure-quotas": {
    category: "Operate",
    scenario: "Capacity",
    role: "Quota planning",
    summary: "Checks quota and capacity constraints before provisioning or scaling Azure resources.",
    prompt: "Check quota for this Azure deployment.",
    highlights: ["Quota", "Capacity", "Regions"],
    icon: "lucide:gauge",
    order: 34
  },
  "azure-ai": {
    category: "AI and data",
    scenario: "Azure AI",
    role: "AI services",
    summary: "Guides Azure AI Search, Speech, OpenAI, Document Intelligence, and related SDK choices.",
    prompt: "Add Azure AI Search to this app.",
    highlights: ["Search", "Speech", "OpenAI"],
    icon: "lucide:brain-circuit",
    order: 40
  },
  "microsoft-foundry": {
    category: "AI and data",
    scenario: "Foundry",
    role: "Agent lifecycle",
    summary: "Deploys, evaluates, monitors, and optimizes Foundry models and agents.",
    prompt: "Deploy and evaluate this agent in Foundry.",
    highlights: ["Agents", "Evals", "Models"],
    icon: "lucide:sparkles",
    order: 41
  },
  "azure-aigateway": {
    category: "AI and data",
    scenario: "AI gateway",
    role: "Gateway patterns",
    summary: "Designs AI gateway patterns for model access, routing, safety, and observability.",
    prompt: "Add an AI gateway for this application.",
    highlights: ["Routing", "Safety", "Observability"],
    icon: "lucide:route",
    order: 42
  },
  "azure-storage": {
    category: "AI and data",
    scenario: "Storage",
    role: "Data services",
    summary: "Guides Azure Storage account, blob, queue, and data access patterns.",
    prompt: "Add Azure Storage to this app.",
    highlights: ["Blob", "Queues", "Managed identity"],
    icon: "lucide:database",
    order: 43
  },
  "azure-kusto": {
    category: "AI and data",
    scenario: "Kusto",
    role: "Analytics",
    summary: "Works with Azure Data Explorer and Kusto queries for operational and analytical scenarios.",
    prompt: "Query this telemetry with Kusto.",
    highlights: ["KQL", "ADX", "Analytics"],
    icon: "lucide:chart-no-axes-combined",
    order: 44
  },
  "azure-messaging": {
    category: "AI and data",
    scenario: "Messaging",
    role: "Eventing",
    summary: "Chooses and configures Azure messaging services for events, queues, and integration flows.",
    prompt: "Choose Azure messaging for this workflow.",
    highlights: ["Service Bus", "Event Grid", "Queues"],
    icon: "lucide:message-square-more",
    order: 45
  },
  "azure-hosted-copilot-sdk": {
    category: "AI and data",
    scenario: "Copilot SDK",
    role: "Hosted copilots",
    summary: "Prepares and deploys hosted Copilot SDK applications with Azure services.",
    prompt: "Prepare this Copilot SDK app for Azure.",
    highlights: ["Copilot SDK", "Hosting", "Identity"],
    icon: "lucide:bot",
    order: 46
  }
};

export async function getSiteData() {
  const [skills, pluginManifest, geminiManifest] = await Promise.all([
    getSkills(),
    readJson<PluginManifest>("plugin.json"),
    readJson<PluginManifest>("gemini-extension.json")
  ]);

  if (pluginManifest.name !== "azure") {
    throw new Error(`Expected plugin.json name to be "azure"; received "${pluginManifest.name ?? "missing"}".`);
  }

  return {
    repository,
    skills,
    categories: getCategoryCounts(skills),
    manifests: {
      plugin: pluginManifest,
      gemini: geminiManifest
    },
    installSurfaces: getInstallSurfaces(pluginManifest.version ?? "latest", geminiManifest.version ?? pluginManifest.version ?? "latest"),
    capabilities: [
      {
        label: "Skills",
        title: "Azure expertise",
        description: "Curated workflows teach agents how Azure work should be planned, validated, deployed, diagnosed, secured, and optimized.",
        icon: "lucide:layers"
      },
      {
        label: "MCP",
        title: "Live Azure tools",
        description: "Azure MCP gives agents structured access to Azure services for inventory, pricing, diagnostics, monitoring, and resource operations.",
        icon: "lucide:wrench"
      },
      {
        label: "Foundry",
        title: "AI specialist",
        description: "Foundry MCP adds model, agent, deployment, and evaluation workflows for teams building AI systems on Microsoft Foundry.",
        icon: "lucide:sparkles"
      }
    ] satisfies Capability[],
    workflows: [
      {
        label: "Prepare",
        prompt: "Prepare this app for Azure.",
        description: "Plan hosting, infrastructure, identity, and deployment files before generation starts.",
        icon: "lucide:clipboard-list"
      },
      {
        label: "Validate",
        prompt: "Validate my Azure deployment files before I run azd up.",
        description: "Catch Azure configuration and infrastructure issues before they become deployment failures.",
        icon: "lucide:badge-check"
      },
      {
        label: "Deploy",
        prompt: "Deploy this project to Azure Container Apps.",
        description: "Run deployment flows with recovery guidance and post-deployment verification.",
        icon: "lucide:rocket"
      },
      {
        label: "Diagnose",
        prompt: "Troubleshoot why my container app is failing health probes.",
        description: "Route from symptoms to Azure logs, metrics, settings, identities, and service-specific checks.",
        icon: "lucide:stethoscope"
      },
      {
        label: "Optimize",
        prompt: "Find cost savings across my Azure subscription.",
        description: "Use pricing, sizing, and resource inventory signals to find practical savings.",
        icon: "lucide:coins"
      },
      {
        label: "Secure",
        prompt: "What role should I assign to let this managed identity read blobs?",
        description: "Choose least-privilege roles and identity patterns for Azure resources and applications.",
        icon: "lucide:key-round"
      }
    ] satisfies Workflow[]
  };
}

async function getSkills(): Promise<SkillCard[]> {
  const skillsRoot = path.join(repositoryRoot, "skills");
  const entries = await readdir(skillsRoot, { withFileTypes: true });
  const cards = await Promise.all(
    entries
      .filter((entry) => entry.isDirectory())
      .map(async (entry) => {
        const filePath = path.join(skillsRoot, entry.name, "SKILL.md");
        const file = await readFile(filePath, "utf8");
        let parsed: matter.GrayMatterFile<string>;

        try {
          parsed = matter(file);
        } catch (error) {
          throw new Error(`Failed to parse frontmatter for ${filePath}: ${error instanceof Error ? error.message : String(error)}`);
        }

        const data = parsed.data as SkillFrontmatter;
        const name = data.name ?? entry.name;
        const description = data.description;

        if (!name || !description) {
          throw new Error(`Skill ${filePath} must include frontmatter name and description.`);
        }

        const profile = skillProfiles[name] ?? defaultSkillProfile(name);

        return {
          name,
          slug: entry.name,
          category: profile.category,
          scenario: profile.scenario,
          role: profile.role,
          summary: profile.summary,
          description: cleanDescription(description),
          version: data.metadata?.version ?? "unversioned",
          prompt: profile.prompt,
          highlights: profile.highlights,
          icon: profile.icon,
          href: `${repository}/blob/main/skills/${entry.name}/SKILL.md`,
          order: profile.order
        };
      })
  );

  return cards.sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
}

function getCategoryCounts(skills: SkillCard[]) {
  const counts = new Map<string, number>();
  for (const skill of skills) {
    counts.set(skill.category, (counts.get(skill.category) ?? 0) + 1);
  }

  return Array.from(counts, ([label, count]) => ({ label, count })).sort((a, b) => a.label.localeCompare(b.label));
}

function defaultSkillProfile(name: string): SkillProfile {
  return {
    category: "Azure skills",
    scenario: toTitleCase(name.replace(/^azure-/, "")),
    role: "Azure workflow",
    summary: "Adds focused Azure guidance, decision support, and guardrails for a specific cloud workflow.",
    prompt: `Use the ${name} skill.`,
    highlights: ["Azure guidance", "MCP-aware", "Guardrails"],
    icon: "lucide:cloud",
    order: 99
  };
}

function cleanDescription(description: string) {
  const withoutRouting = description.split(/\b(?:WHEN|USE FOR|DO NOT USE FOR):/u)[0]?.trim() ?? description.trim();
  return withoutRouting.length > 190 ? `${withoutRouting.slice(0, 187).trimEnd()}...` : withoutRouting;
}

function getInstallSurfaces(pluginVersion: string, geminiVersion: string): InstallSurface[] {
  return [
    {
      id: "apm",
      name: "APM",
      shortName: "APM",
      detail: "Install once across compatible agent hosts from the repository apm.yml.",
      command: "apm install microsoft/azure-skills",
      badge: pluginVersion,
      status: "Multi-host",
      language: "bash",
      title: "Install with APM",
      icon: "lucide:package",
      notes: ["Best path when you use multiple harnesses.", "Uses the repository package definition.", "Keeps skills and MCP configuration aligned."]
    },
    {
      id: "copilot",
      name: "GitHub Copilot CLI",
      shortName: "Copilot CLI",
      detail: "Add the Azure Skills marketplace, then install the Azure plugin in Copilot CLI.",
      command: "/plugin marketplace add microsoft/azure-skills\n/plugin install azure@azure-skills",
      badge: pluginVersion,
      status: "Plugin",
      language: "bash",
      title: "Install in Copilot CLI",
      icon: "lucide:terminal",
      notes: ["Use /plugin update azure@azure-skills to update.", "Run /mcp show to verify Azure MCP is configured.", "Authenticate Azure CLI before live resource operations."]
    },
    {
      id: "vscode",
      name: "Visual Studio Code",
      shortName: "VS Code",
      detail: "Install the Azure MCP extension, which brings Azure MCP and Azure skills into GitHub Copilot.",
      command: "code --install-extension ms-azuretools.vscode-azure-mcp-server",
      badge: "Extension",
      status: "Marketplace",
      language: "bash",
      title: "Install VS Code extension",
      icon: "lucide:code-2",
      notes: ["Requires Git CLI for skill installation.", "Restart VS Code if Copilot does not discover the skills.", "Use az login before asking for live Azure resources."]
    },
    {
      id: "claude",
      name: "Claude Code",
      shortName: "Claude",
      detail: "Install the Azure plugin from the official Claude Code plugin marketplace.",
      command: "/plugin install azure@claude-plugins-official",
      badge: pluginVersion,
      status: "Marketplace",
      language: "bash",
      title: "Install in Claude Code",
      icon: "lucide:bot",
      notes: ["Search for azure in /plugin if you prefer interactive install.", "Update with /plugin update azure@claude-plugins-official.", "Node.js 18+ is required for MCP server startup."]
    },
    {
      id: "gemini",
      name: "Gemini CLI",
      shortName: "Gemini",
      detail: "Install the Azure Skills extension directly from the repository.",
      command: "gemini extensions install https://github.com/microsoft/azure-skills",
      badge: geminiVersion,
      status: "Extension",
      language: "bash",
      title: "Install in Gemini CLI",
      icon: "lucide:sparkle",
      notes: ["The extension configures Azure MCP through npx.", "Use az login before resource-backed prompts.", "Reinstall or update when repository guidance changes."]
    },
    {
      id: "cursor",
      name: "Cursor",
      shortName: "Cursor",
      detail: "Install the Azure plugin from Cursor Marketplace or Cursor settings.",
      command: "Open Cursor Settings > Plugins, search for Azure, then install the Azure plugin.",
      badge: "Marketplace",
      status: "Plugin",
      language: "text",
      title: "Install in Cursor",
      icon: "lucide:mouse-pointer-2",
      notes: ["The marketplace listing points back to microsoft/azure-skills.", "Reload Cursor if skills are not discovered immediately.", "Azure MCP still needs local Node.js and Azure authentication."]
    },
    {
      id: "codex",
      name: "Codex CLI",
      shortName: "Codex",
      detail: "Add the marketplace, browse plugins, and install the Azure plugin.",
      command: "codex plugin marketplace add microsoft/azure-skills\n# Then run /plugins and install azure",
      badge: "Plugin",
      status: "CLI",
      language: "bash",
      title: "Install in Codex CLI",
      icon: "lucide:square-terminal",
      notes: ["Use /skills to enable or disable individual Azure skills.", "A CLI-installed plugin is also available in the Codex app.", "Keep Node.js 18+ available for MCP."]
    },
    {
      id: "intellij",
      name: "IntelliJ IDEA",
      shortName: "IntelliJ",
      detail: "Enable skills in the GitHub Copilot plugin, then install Azure Skills through the Azure Toolkit or skills CLI.",
      command: "npx skills add https://github.com/microsoft/azure-skills/tree/main/.github/plugins/azure-skills/skills -a github-copilot -g -y",
      badge: "Skills",
      status: "JetBrains",
      language: "bash",
      title: "Install for IntelliJ IDEA",
      icon: "lucide:blocks",
      notes: ["Requires the GitHub Copilot plugin with Skills enabled.", "Azure Toolkit can prompt for installation after restart.", "Git and Node.js must be available on PATH."]
    }
  ];
}

async function readJson<T>(relativePath: string): Promise<T> {
  const content = await readFile(path.join(repositoryRoot, relativePath), "utf8");
  return JSON.parse(content) as T;
}

function toTitleCase(value: string) {
  return value
    .split(/[-_\s]+/u)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}
