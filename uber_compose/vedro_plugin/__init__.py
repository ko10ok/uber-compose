"""
Vedro plugin integration for uber-compose.

Enabled plugin (in vedro.cfg) catches stage before tests run (StartupEvent) and before each test run (ScenarioRunEvent).

On each stage it starts testing environment required by selected tests.
"""
