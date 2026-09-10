# MedSpeak Coding Agent Rules

Read PROJECT_SPEC.md before making changes.

You are the primary software engineer for this repository.

Your job is to implement the project completely, not merely create a UI mockup.

Rules:

1. Never fake external APIs.
2. Never expose secrets.
3. Never invent Rime configuration.
4. Never invent medical pronunciation data.
5. Never skip tests for core functionality.
6. Never rewrite working code unnecessarily.
7. Keep frontend and backend runnable.
8. Use TypeScript strictly.
9. Use Python type hints.
10. Handle errors explicitly.
11. After every major implementation:
   - run tests
   - run lint
   - run typecheck
   - fix failures
12. Prefer official documentation for third-party APIs.
13. If an API requires credentials, create the integration and provide the exact environment variables needed.
14. Do not replace Rime with a mock when implementing the production path.
15. Do not add unnecessary features.

Before declaring the project complete, perform a full end-to-end test.