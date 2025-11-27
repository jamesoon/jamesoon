# Lessons Learned

This document records critical lessons, bug fixes, and architectural decisions to prevent future regressions.

## Template

### [YYYY-MM-DD] [Topic/Error Name]
- **Context**: What were we trying to do?
- **Issue**: What went wrong? (Paste error logs if applicable)
- **Solution**: How did we fix it?
- **Prevention**: How do we ensure this doesn't happen again?

---

## [2025-11-27] Lambda Deployment Errors (Example)
- **Context**: Deploying the market data updater lambda.
- **Issue**: Deployment failed due to package size exceeding AWS limits or missing dependencies in the layer.
- **Solution**: [Placeholder: Describe the actual solution used, e.g., using Docker container images or splitting layers]
- **Prevention**: Always check package size before deployment. Use `scripts/check_lambda_size.sh` (if it exists).

## [2025-11-27] Agent Context Missing
- **Context**: Agents were making changes without knowing project standards.
- **Issue**: Inconsistent code style and repeated errors.
- **Solution**: Implemented `AGENT_INSTRUCTIONS.md` and `.cursorrules`.
- **Prevention**: Agents are now instructed to read these files first.
