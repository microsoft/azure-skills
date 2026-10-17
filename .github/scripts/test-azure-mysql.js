const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const repositoryRoot = path.resolve(__dirname, "..", "..");
const pluginRoot = path.join(repositoryRoot, ".github", "plugins", "azure-skills");
const skillRoots = [
  path.join(repositoryRoot, "skills"),
  path.join(pluginRoot, "skills"),
];
const referenceFiles = [
  "tools.md",
  "deployment.md",
  "connectivity.md",
  "troubleshooting.md",
  "reliability.md",
];
const sharedParameters = ["server", "resource-group", "subscription"];
const dataParameters = ["server", "database", "user"];
// Argument snapshot only; transport/authentication capabilities need a separate preflight.
const commandSchemas = {
  mysql_list: {
    required: [],
    allowed: [...sharedParameters, "database", "user"],
  },
  mysql_database_query: {
    required: [...dataParameters, "query"],
    allowed: [...dataParameters, "query"],
  },
  mysql_table_schema_get: {
    required: [...dataParameters, "table"],
    allowed: [...dataParameters, "table"],
  },
  mysql_server_config_get: {
    required: ["server", "resource-group"],
    allowed: sharedParameters,
  },
  mysql_server_param_get: {
    required: ["server", "resource-group", "param"],
    allowed: [...sharedParameters, "param"],
  },
  mysql_server_param_set: {
    required: ["server", "resource-group", "param", "value"],
    allowed: [...sharedParameters, "param", "value"],
  },
};

function read(root, ...parts) {
  return fs.readFileSync(path.join(root, ...parts), "utf8");
}

function listFiles(directory, relative = "") {
  return fs.readdirSync(path.join(directory, relative), { withFileTypes: true })
    .flatMap(entry => {
      const entryPath = path.join(relative, entry.name);
      return entry.isDirectory()
        ? listFiles(directory, entryPath)
        : [entryPath];
    })
    .sort();
}

function localLinks(file) {
  return [...fs.readFileSync(file, "utf8").matchAll(/\[[^\]]*\]\(([^)\s]+)\)/g)]
    .map(match => match[1])
    .filter(link => !/^(?:https?:|mailto:|#)/.test(link))
    .map(link => path.resolve(path.dirname(file), link.split("#")[0]));
}

function assertReadOnlyQuery(query) {
  assert.match(query, /^\s*SELECT\b/i);
  assert.doesNotMatch(query, /;[\s\S]*\S/);
  assert.doesNotMatch(query, /--|\/\*|\b(?:INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP|TRUNCATE|CALL|INTO|SLEEP|BENCHMARK|GET_LOCK|FOR\s+SHARE|LOCK\s+IN)\b/i);
  assert.doesNotMatch(query, /\bSELECT\s+\*/i);
  if (/\bFROM\b/i.test(query)) {
    assert.match(query, /\bLIMIT\s+\d+\s*;?\s*$/i);
    assert.match(query, /\bORDER\s+BY\b/i);
  }
}

test("both plugin manifests discover the MySQL skill with valid metadata", () => {
  const manifests = [
    [repositoryRoot, "plugin.json"],
    [pluginRoot, path.join(".plugin", "plugin.json")],
  ];
  for (const [root, manifestPath] of manifests) {
    const manifest = JSON.parse(read(root, manifestPath));
    const entry = read(root, manifest.skills, "azure-mysql", "SKILL.md");
    const frontmatter = entry.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
    assert.ok(frontmatter, "Skill must have YAML frontmatter");
    assert.match(frontmatter[1], /^name: azure-mysql$/m);
    assert.match(frontmatter[1], /^license: MIT$/m);
    assert.match(frontmatter[1], /^metadata:\r?\n  author: \S.+\r?\n  version: "\d+\.\d+\.\d+"$/m);
    const description = frontmatter[1].match(/^description: (".*")$/m);
    assert.ok(description, "Routing description must be a quoted string");
    const value = JSON.parse(description[1]);
    assert.ok(value.length <= 1024, "Description must fit skill metadata limits");
    assert.match(value, /Flexible Server/);
    assert.match(value, /USE FOR:/);
    assert.match(value, /DO NOT USE FOR:/);
    assert.ok(entry.split("\n").length <= 500, "Keep the entry point progressively loaded");
  }
});

test("root and packaged skill file sets and contents match exactly", () => {
  const rootSkill = path.join(skillRoots[0], "azure-mysql");
  const packagedSkill = path.join(skillRoots[1], "azure-mysql");
  const files = listFiles(rootSkill);
  assert.deepEqual(files, listFiles(packagedSkill));
  for (const file of files) {
    assert.equal(read(rootSkill, file), read(packagedSkill, file), file);
  }
  for (const file of [
    path.join("azure-prepare", "references", "architecture.md"),
    path.join("azure-prepare", "references", "research.md"),
    path.join("azure-prepare", "references", "services", "mysql", "README.md"),
    path.join("azure-diagnostics", "SKILL.md"),
  ]) {
    assert.equal(read(skillRoots[0], file), read(skillRoots[1], file), file);
  }
});

test("every MySQL reference exists, is linked, and stays within the installed skills", () => {
  for (const skillsRoot of skillRoots) {
    const directory = path.join(skillsRoot, "azure-mysql");
    const files = listFiles(directory);
    assert.deepEqual(
      files,
      ["SKILL.md", ...referenceFiles.map(file => path.join("references", file))].sort(),
    );
    const visited = new Set();
    const pending = [path.join(directory, "SKILL.md")];
    while (pending.length > 0) {
      const file = pending.pop();
      if (visited.has(file)) {
        continue;
      }
      visited.add(file);
      for (const target of localLinks(file)) {
        assert.ok(fs.existsSync(target), `${file} links to missing ${target}`);
        assert.ok(!path.relative(skillsRoot, target).startsWith(".."), target);
        if (target.startsWith(`${directory}${path.sep}`)) {
          pending.push(target);
        }
      }
    }
    for (const file of files) {
      assert.ok(visited.has(path.join(directory, file)), `Unreachable reference: ${file}`);
    }
    const service = path.join(skillsRoot, "azure-prepare", "references", "services", "mysql", "README.md");
    for (const target of localLinks(service)) {
      assert.ok(fs.existsSync(target), `${service} links to missing ${target}`);
      assert.ok(!path.relative(skillsRoot, target).startsWith(".."), target);
    }
  }
});

test("all six MCP command examples match the documented argument snapshot", () => {
  const tools = read(skillRoots[0], "azure-mysql", "references", "tools.md");
  const examples = [...tools.matchAll(/```json\r?\n([\s\S]*?)```/g)];
  const seen = new Set();
  assert.ok(examples.length >= Object.keys(commandSchemas).length);
  for (const [, json] of examples) {
    const example = JSON.parse(json);
    assert.deepEqual(Object.keys(example).sort(), ["command", "intent", "parameters"]);
    assert.equal(typeof example.intent, "string");
    assert.ok(example.intent.trim().length > 0);
    const schema = commandSchemas[example.command];
    assert.ok(schema, `Unknown MySQL command: ${example.command}`);
    seen.add(example.command);
    for (const required of schema.required) {
      assert.ok(Object.hasOwn(example.parameters, required), `${example.command}: missing ${required}`);
    }
    for (const [name, value] of Object.entries(example.parameters)) {
      assert.ok(schema.allowed.includes(name), `${example.command}: unknown parameter ${name}`);
      assert.equal(typeof value, "string");
      assert.ok(value.trim().length > 0);
    }
    if (example.command === "mysql_list" && example.parameters.server) {
      assert.ok(example.parameters.user, "Database/table discovery needs a database user");
    }
    if (example.command === "mysql_list" && example.parameters.database) {
      assert.ok(example.parameters.server, "Table discovery needs a server");
    }
    if (example.command === "mysql_database_query") {
      assertReadOnlyQuery(example.parameters.query);
    }
  }
  assert.deepEqual([...seen].sort(), Object.keys(commandSchemas).sort());
});

test("SQL inspection examples are single, bounded, non-locking SELECT statements", () => {
  let count = 0;
  for (const file of referenceFiles) {
    const content = read(skillRoots[0], "azure-mysql", "references", file);
    for (const [, query] of content.matchAll(/```sql\r?\n([\s\S]*?)```/g)) {
      assertReadOnlyQuery(query.trim());
      count += 1;
    }
  }
  assert.ok(count > 0, "Include a concrete safe inspection example");
});

test("preparation and diagnostics route to MySQL guidance in both distributions", () => {
  for (const skillsRoot of skillRoots) {
    const serviceLink = "services/mysql/README.md";
    assert.ok(read(skillsRoot, "azure-prepare", "references", "architecture.md").includes(serviceLink));
    const research = read(skillsRoot, "azure-prepare", "references", "research.md");
    assert.ok(research.includes(serviceLink));
    assert.match(research, /`azure-mysql`/);
    const diagnostics = read(skillsRoot, "azure-diagnostics", "SKILL.md");
    const description = JSON.parse(diagnostics.match(/^description: (".*")$/m)[1]);
    assert.ok(description.length <= 1024, "Diagnostics routing metadata must fit skill limits");
    assert.ok(diagnostics.includes("../azure-mysql/references/troubleshooting.md"));
    assert.match(diagnostics, /`azure-mysql`/);
  }
});

test("data-plane examples require a verified TLS capability preflight", () => {
  for (const skillsRoot of skillRoots) {
    const entry = read(skillsRoot, "azure-mysql", "SKILL.md");
    const tools = read(skillsRoot, "azure-mysql", "references", "tools.md");
    const preflight = tools.match(/## Data-plane Preflight\r?\n([\s\S]*?)(?=\r?\n## )/);
    assert.ok(preflight, "A data-plane gate must precede the examples");
    assert.match(entry, /Prefer Azure MCP for management-plane operations/);
    assert.ok(entry.includes("references/tools.md#data-plane-preflight"));
    assert.match(preflight[1], /mysql_list.*server/);
    assert.match(preflight[1], /mysql_table_schema_get/);
    assert.match(preflight[1], /mysql_database_query/);
    assert.match(preflight[1], /3\.0\.0/);
    assert.match(preflight[1], /SslMode\.Required/);
    assert.match(preflight[1], /does not validate the CA or hostname/);
    assert.match(preflight[1], /Do not execute these data-plane commands in 3\.0\.0/);
    assert.match(preflight[1], /verified native client/);
    assert.ok(tools.includes("Azure.Mcp.Server-3.0.0"));
  }
});

test("MCP authentication requires the current credential's mapped Entra identity", () => {
  for (const skillsRoot of skillRoots) {
    const tools = read(skillsRoot, "azure-mysql", "references", "tools.md");
    const connectivity = read(skillsRoot, "azure-mysql", "references", "connectivity.md");
    assert.match(tools, /current Azure credential/);
    assert.match(tools, /Entra authentication must already be enabled/);
    assert.match(tools, /user.*does not select another Azure identity/);
    assert.match(tools, /native-only.*verified native client/i);
    assert.ok(connectivity.includes("tools.md#data-plane-preflight"));
    for (const [, json] of tools.matchAll(/```json\r?\n([\s\S]*?)```/g)) {
      const example = JSON.parse(json);
      if (example.parameters.user) {
        assert.equal(example.parameters.user, "ENTRA_DATABASE_USER");
      }
    }
  }
});

test("schema guidance supplements column-only output with scoped index and constraint queries", () => {
  for (const skillsRoot of skillRoots) {
    const tools = read(skillsRoot, "azure-mysql", "references", "tools.md");
    const schemaRow = tools.split(/\r?\n/).find(line => line.startsWith("| `mysql_table_schema_get`"));
    assert.match(schemaRow, /Column names and data types only/);
    const queries = [...tools.matchAll(/```sql\r?\n([\s\S]*?)```/g)].map(([, query]) => query);
    const indexes = queries.find(query => query.includes("information_schema.STATISTICS"));
    const constraints = queries.find(query => query.includes("information_schema.TABLE_CONSTRAINTS"));
    for (const query of [indexes, constraints]) {
      assert.ok(query, "Index and constraint inspection must have explicit examples");
      assertReadOnlyQuery(query.trim());
      assert.match(query, /TABLE_SCHEMA = DATABASE\(\)/);
      assert.match(query, /TABLE_NAME = 'TABLE_NAME'/);
    }
    assert.ok(constraints.includes("information_schema.KEY_COLUMN_USAGE"));
    assert.ok(constraints.includes("REFERENCED_COLUMN_NAME"));
    assert.match(tools, /Missing fields are not evidence/);
  }
});

test("Azure plugin release versions agree with the changelog and advance the cached release", () => {
  const manifests = [
    path.join(repositoryRoot, "plugin.json"),
    path.join(repositoryRoot, ".claude-plugin", "plugin.json"),
    path.join(pluginRoot, ".plugin", "plugin.json"),
    path.join(pluginRoot, ".claude-plugin", "plugin.json"),
    path.join(pluginRoot, ".cursor-plugin", "plugin.json"),
  ];
  const versions = manifests.map(file => JSON.parse(fs.readFileSync(file, "utf8")).version);
  assert.equal(new Set(versions).size, 1, "Azure plugin hosts must ship the same release");
  assert.notEqual(versions[0], "1.2.95", "Existing cached installations need a new plugin version");
  const changelog = read(pluginRoot, "CHANGELOG.md");
  assert.equal(changelog.match(/^## (\d+\.\d+\.\d+)$/m)[1], versions[0]);
  assert.ok(changelog.includes("`azure-mysql`"), "Record the new skill in the release history");
});

test("Entra client guidance guards against truncating long tokens", () => {
  for (const skillsRoot of skillRoots) {
    const connectivity = read(skillsRoot, "azure-mysql", "references", "connectivity.md");
    assert.match(connectivity, /MySQL Shell 8\.4\.10/);
    assert.ok(connectivity.includes("--passwords-from-stdin"));
    assert.match(connectivity, /127/);
    assert.match(connectivity, /synthetic/i);
    assert.match(connectivity, /entire token in memory/);
    assert.ok(connectivity.includes("mysql/mysql-shell"));
  }
});
