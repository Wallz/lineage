from django.core.cache import cache
import hashlib
import json
from sqlalchemy.engine import RowMapping


def convert_rowmapping_to_dict(obj):
    if isinstance(obj, list):
        return [dict(row) for row in obj]
    elif isinstance(obj, RowMapping):
        return dict(obj)
    return obj


def cache_lineage_result(timeout=300, use_cache=True):
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time
            import logging
            logger = logging.getLogger(__name__)
            
            # Se o cache não deve ser usado, execute a função normalmente
            if not use_cache:
                result = func(*args, **kwargs)
                result_converted = convert_rowmapping_to_dict(result)
                return result_converted
            
            # Gera uma chave única com base na função + argumentos
            key_base = f"{func.__module__}.{func.__name__}:{json.dumps(args)}:{json.dumps(kwargs)}"
            key = f"lineage_cache:{hashlib.md5(key_base.encode()).hexdigest()}"

            # Tenta pegar do cache com timeout
            try:
                cached = cache.get(key)
                if cached is not None:
                    return cached
            except Exception as e:
                logger.warning(f"Erro ao acessar cache: {e}")

            # Se não tiver, executa e armazena no cache com timeout de execução
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log se a query demorou muito
                if execution_time > 2:
                    logger.warning(f"Query {func.__name__} demorou {execution_time:.2f}s")

                # Converte o resultado antes de salvar e retornar
                result_converted = convert_rowmapping_to_dict(result)
                
                # Tenta salvar no cache, mas não falha se der erro
                try:
                    cache.set(key, result_converted, timeout=timeout)
                except Exception as e:
                    logger.warning(f"Erro ao salvar no cache: {e}")
                
                return result_converted
                
            except Exception as e:
                logger.error(f"Erro ao executar query {func.__name__}: {e}")
                # Retorna resultado vazio em caso de erro
                return [] if 'top_' in func.__name__ or 'players_online' in func.__name__ else None
                
        return wrapper
    return decorator
