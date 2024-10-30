from app import app
from app import rq
import redis
from redis import Redis
from rq import Queue, Worker, Retry
from rq.job import Job
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError
from elasticsearch import ConnectionTimeout
from app.search import add_to_index
import logging
from rq.registry import FailedJobRegistry
from rq.timeouts import JobTimeoutException
from redis import RedisError, ConnectionError
import time



redis = Redis()
queue = Queue(connection=redis, default_timeout=600)


def reprocess_failed_jobs():
    try:
        registry = FailedJobRegistry(queue=queue)
        failed_jobs = registry.get_job_ids()
        time.sleep(2)
        if not failed_jobs:
            app.logger.info("No failed jobs found in the queue.")
            return
        app.logger.info(f"Found {len(failed_jobs)} failed jobs. Attempting to reprocess.")
        for job_id in failed_jobs:
            try:
                job = Job.fetch(job_id, connection=redis)
            except NoSuchJobError:
                app.logger.warning(f"Job {job_id} no longer exists in Redis.")
                continue
            retries = job.meta.get('retries', 0)
            app.logger.info(retries)
            if retries > 5: #Retry Limit
                job.cancel()
                time.sleep(2)
                app.logger.error(f"Job {job_id} was canceled due to reaching the retry limit. Manual intervention is required. Please check the CanceledJobRegistry.")
                continue
            retries += 1
            job.meta['retries'] = retries
            job.save_meta()
            time.sleep(2)
            try:  
                app.logger.info(f"Retrying Job {job_id}...")
                registry.requeue(job_id)  
            except (ElasticConnectionError, ConnectionTimeout) as e:
                app.logger.error(f"Job {job_id} failed again due to Elasticsearch connection error.")
                raise e
            except Exception as e:
                app.logger.error(f"Job {job_id} failed again due to an exception.")
                raise e
    except JobTimeoutException as e:
        app.logger.error(f"Job timeout while trying to remove {model} from Elasticsearch: {str(e)}")
        raise e
    except ConnectionError as e:
        app.logger.error(f"Redis connection error: {str(e)}")
        raise e
    except RedisError as e:
        app.logger.error(f"Redis error: {str(e)}")
        raise e
