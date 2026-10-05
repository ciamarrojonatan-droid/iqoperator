"""Sync opcional de logs/trades para um dataset do Hugging Face (bucket).

Usa HF_TOKEN + HF_DATASET_REPO (ex: microfactx/iqoperator-trades).
Se não configurado, vira no-op. Fail-open: nunca quebra o bot.

Railway sem disco: ative isso e o trades_live.csv sobrevive a restarts.
"""
import logging
import os
import threading
import time

log = logging.getLogger("iqrobot.hf")


def _configured() -> bool:
    return bool(os.getenv("HF_TOKEN") and os.getenv("HF_DATASET_REPO"))


_repo_ensured = False

def sync_file(local_path: str, repo_path: str | None = None):
    """Upload em thread daemon; silencioso se não configurado."""
    if not _configured():
        return
    if not os.path.exists(local_path):
        return
    repo_path = repo_path or os.path.basename(local_path)
    token = os.getenv("HF_TOKEN", "")
    repo_id = os.getenv("HF_DATASET_REPO", "")

    def _do():
        global _repo_ensured
        try:
            from huggingface_hub import HfApi
            api = HfApi(token=token)
            # garante dataset existe (cria se faltar, idempotente)
            if not _repo_ensured:
                try:
                    api.create_repo(repo_id, repo_type="dataset", exist_ok=True)
                except Exception:
                    pass
                _repo_ensured = True
                
            api.upload_file(
                path_or_fileobj=local_path,
                path_in_repo=repo_path,
                repo_id=repo_id,
                repo_type="dataset",
            )
            log.info(f"[HF SYNC] {local_path} -> {repo_id}/{repo_path}")
        except Exception as e:
            log.warning(f"[HF SYNC] falhou {local_path}: {e}")

    threading.Thread(target=_do, daemon=True).start()

def download_file(local_path: str, repo_path: str | None = None) -> bool:
    if not _configured():
        return False
    repo_path = repo_path or os.path.basename(local_path)
    token = os.getenv("HF_TOKEN", "")
    repo_id = os.getenv("HF_DATASET_REPO", "")
    try:
        from huggingface_hub import hf_hub_download
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        dl_path = hf_hub_download(repo_id=repo_id, filename=repo_path, repo_type="dataset", token=token)
        import shutil
        shutil.copy(dl_path, local_path)
        log.info(f"[HF SYNC] {repo_id}/{repo_path} baixado p/ {local_path}")
        return True
    except Exception as e:
        log.warning(f"[HF SYNC] Nao foi possivel baixar {repo_path}: {e}")
        return False
    repo_path = repo_path or os.path.basename(local_path)
    token = os.getenv("HF_TOKEN", "")
    repo_id = os.getenv("HF_DATASET_REPO", "")
    try:
        from huggingface_hub import hf_hub_download
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        dl_path = hf_hub_download(repo_id=repo_id, filename=repo_path, repo_type="dataset", token=token)
        import shutil
        shutil.copy(dl_path, local_path)
        log.info(f"[HF SYNC] {repo_id}/{repo_path} baixado p/ {local_path}")
        return True
    except Exception as e:
        log.warning(f"[HF SYNC] Nao foi possivel baixar {repo_path}: {e}")
        return False



