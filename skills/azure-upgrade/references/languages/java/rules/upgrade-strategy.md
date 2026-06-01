# Upgrade Strategy

- **Incremental upgrades**: Stepwise dependency upgrades to avoid large jumps breaking builds.
- **Minimal changes**: Only upgrade dependencies essential for compatibility with the modern Azure SDKs.
- **Risk-first**: Handle EOL/challenging deps early in isolated steps.
- **Necessary/Meaningful steps only**: Each step MUST change code/config. NO steps for pure analysis/validation. Merge small related changes. **Test**: "Does this step modify project files?"
- **Automation tools**: Use automation tools like OpenRewrite for efficiency; always verify output. For BOM upgrades, run the [`scripts/upgrade_bom.py`](../scripts/upgrade_bom.py) script in the parent folder when Python 3.10+ is available; if Python is not available or the script fails, manually resolve the BOM version and follow the **Manual Fallback** sections in [bom-maven.md](../bom-migration/bom-maven.md) / [bom-gradle.md](../bom-migration/bom-gradle.md) instead (see [Migration Guidelines](../INSTRUCTION.md#maven-use-the-upgrade_bom-script)).
- **Successor preference**: Compatible successor > Adapter pattern > Code rewrite.
- **Build tool compatibility**: Check Maven/Gradle version compatibility with the project's JDK. Upgrade the build tool (including wrapper) if the current version does not support the JDK.
- **Temporary errors OK**: Steps may pass with known errors if resolved later or pre-existing.
