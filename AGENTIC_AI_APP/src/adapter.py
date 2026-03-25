import asyncio
import json
import os
from confluent_kafka import Consumer, Producer
from langgraph.checkpoint.redis import RedisSaver
from redis import Redis
from langchain_core.messages import HumanMessage
from .graph import get_graph

APP_NAME = os.getenv("APP_NAME", "unknown-app")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_INPUT_TOPIC = os.getenv("KAFKA_INPUT_TOPIC", f"{APP_NAME}-requests")
KAFKA_OUTPUT_TOPIC = os.getenv("KAFKA_OUTPUT_TOPIC", f"{APP_NAME}-responses")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Setup Redis connection
redis_conn = Redis.from_url(REDIS_URL)

producer_conf = {'bootstrap.servers': KAFKA_BOOTSTRAP}
producer = Producer(producer_conf)

async def process_message(user_id: str, text: str):
    # Scope checkpointer to the app
    thread_identifier = f"{APP_NAME}:{user_id}"
    config = {"configurable": {"thread_id": thread_identifier}}
    
    checkpointer = RedisSaver(redis_conn)
    app_graph = get_graph(checkpointer)

    result = await asyncio.to_thread(
        app_graph.invoke,
        {"messages": [HumanMessage(content=text)]},
        config
    )
    
    # Extract response
    last_message = result['messages'][-1].content
    
    # Produce back to Kafka
    payload = json.dumps({
        "user_id": user_id,
        "response": last_message
    })
    producer.produce(KAFKA_OUTPUT_TOPIC, value=payload)
    producer.poll(0)

async def start_adapter_loop():
    consumer_conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP,
        'group.id': f'{APP_NAME}-group',
        'auto.offset.reset': 'latest'
    }
    
    consumer = Consumer(consumer_conf)
    consumer.subscribe([KAFKA_INPUT_TOPIC])
    
    print(f"[{APP_NAME}] Agent adapter started, waiting for messages on {KAFKA_INPUT_TOPIC}...")
    
    try:
        while True:
            msg = consumer.poll(0.1)
            if msg is None:
                await asyncio.sleep(0.1)
                continue
            if msg.error():
                continue
                
            val = msg.value().decode('utf-8')
            try:
                data = json.loads(val)
                user_id = data.get("user_id")
                text = data.get("text")
                if user_id and text:
                    asyncio.create_task(process_message(user_id, text))
            except Exception as e:
                print(f"[{APP_NAME}] Error processing message in adapter: {e}")
    except asyncio.CancelledError:
        pass
    finally:
        consumer.close()
