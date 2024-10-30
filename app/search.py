from app import app
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError
from elasticsearch import ConnectionTimeout
import logging
import redis
from app import rq
from rq.timeouts import JobTimeoutException
import time



class ElasticsearchError(Exception):
    pass


def add_to_index(index, model):
    try:
        if not app.elasticsearch:
            app.logger.warning("Elasticsearch is not configured.")
            return
        payload = {}
        for field in model.__searchable__:
            payload[field] = getattr(model, field)
        app.elasticsearch.index(index=index, id=model.id, document=payload)
        app.logger.info(f"Successfully indexed {model} in Elasticsearch.")
    except (ElasticConnectionError, ConnectionTimeout) as e:
        app.logger.error(f"Elasticsearch connection failed while indexing: {str(e)}.")
        raise ElasticsearchError(f"Elasticsearch error: {str(e)}")
    except JobTimeoutException as e:
        app.logger.error(f"Job timeout while trying to remove {model} from Elasticsearch: {str(e)}")
        raise JobTimeoutException(f"Job exceeded the maximum timeout of {e.timeout} seconds.")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {str(e)}")
        raise e



def remove_from_index(index, model):
    try:
        if not app.elasticsearch:
            app.logger.warning("Elasticsearch is not configured.")
            return
        app.elasticsearch.delete(index=index, id=model.id)
        app.logger.info(f"Successfully removed {model} from index {index}.")
    except (ElasticConnectionError, ConnectionTimeout) as e:
        app.logger.error(f"Elasticsearch connection failed while deleting: {str(e)}. Retrying...")
        raise ElasticsearchError(f"Elasticsearch error: {str(e)}")
    except JobTimeoutException as e:
        app.logger.error(f"Job timeout while trying to remove {model} from Elasticsearch: {str(e)}")
        raise JobTimeoutException(f"Job exceeded the maximum timeout of {e.timeout} seconds.")
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {str(e)}")
        raise e



def query_index(index, query, page, per_page):
    if not app.elasticsearch:
        app.logger.warning("Elasticsearch is not configured.")
        return [], 0
    try:
        search = app.elasticsearch.search(
            index=index,
            query={'multi_match': {'query': query, 'fields': ['*']}},
            from_=(page - 1) * per_page,
            size=per_page)
        ids = [int(hit['_id']) for hit in search['hits']['hits']]
        total_hits = search['hits']['total']['value']
        app.logger.info(f"Query successful. Found {total_hits} matches for '{query}' in index '{index}'.")
        return ids, total_hits
    except (ElasticConnectionError, ConnectionTimeout) as e:
        app.logger.error(f"Elasticsearch query failed: {str(e)}")
        return [], -1