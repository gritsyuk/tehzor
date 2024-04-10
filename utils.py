import time


def time_execution(func):
    async def wrapped(*args, **kwargs):
        print("Start ....")
        start = time.time()
        result = await func(*args, **kwargs)
        task_time = round(time.time() - start, 2)
        print(f"Time execution: {task_time} sec")
        return result
    
    return wrapped  