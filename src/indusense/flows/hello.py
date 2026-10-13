"""M29 TP socle — premier flow Prefect « hello ».

Un @flow orchestre une @task avec retries. Exécution 100 % locale : on appelle
directement la fonction décorée (pas de flow.run() en Prefect 3, pas de serveur ni de Cloud).

    uv run python -m indusense.flows.hello   # -> pong:indusense + run Completed
"""

from __future__ import annotations

from prefect import flow, get_run_logger, task


# Task = étape unitaire. retries=2 : en cas d'exception, Prefect la relance jusqu'à 2 fois
# (utile pour une erreur TRANSITOIRE ; inutile pour une erreur déterministe).
@task(retries=2, retry_delay_seconds=1)
def ping(name: str) -> str:
    """Répond « pong:<name> » : stand-in d'une vraie étape (ingest, predict...)."""
    return f"pong:{name}"


# Flow = orchestration des tasks ; chaque run est tracé (état, logs, durée).
@flow(name="hello-indusense", log_prints=True)
def hello_flow(name: str = "indusense") -> str:
    """Appelle la task et loggue son résultat."""
    result = ping(name)
    get_run_logger().info("Résultat de la task : %s", result)
    return result


if __name__ == "__main__":
    print(hello_flow())
