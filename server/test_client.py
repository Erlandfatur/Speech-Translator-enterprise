import json
import time
import base64
import asyncio
import numpy as np
import websockets

async def run_benchmark_test():
    uri = "ws://localhost:8000/ws/translate?room_id=test-room-101&user_id=speaker-A"
    print("Connecting to Real-time Translation Server benchmark...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            
            # Send configuration
            config_msg = {
                "type": "config",
                "config": {
                    "spoken_lang": "en",
                    "target_lang": "id",
                    "tts_enabled": True
                }
            }
            await websocket.send(json.dumps(config_msg))
            
            # Generate 1 second of sample PCM audio data (speech)
            sample_rate = 16000
            duration = 1.0
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            sine_wave = (np.sin(2 * np.pi * 440 * t) * 16384).astype(np.int16)
            
            payload = {
                "type": "audio_chunk",
                "audio_b64": base64.b64encode(sine_wave.tobytes()).decode('utf-8')
            }
            
            start_time = time.time()
            await websocket.send(json.dumps(payload))
            print("Speech chunk sent.")
            
            # Send 2 seconds of silence in small chunks to trigger VAD timeout
            silence_chunk = np.zeros(int(sample_rate * 0.1), dtype=np.int16)
            silence_b64 = base64.b64encode(silence_chunk.tobytes()).decode('utf-8')
            silence_payload = {
                "type": "audio_chunk",
                "audio_b64": silence_b64
            }
            
            for _ in range(20):
                await websocket.send(json.dumps(silence_payload))
                await asyncio.sleep(0.1)
                
            print("Silence chunks sent. Waiting for response...")
            
            response_data = await websocket.recv()
            elapsed_ms = (time.time() - start_time) * 1000.0
            
            resp = json.loads(response_data)
            print("\n--- BENCHMARK RESULTS ---")
            print(f"Response Received Type: {resp.get('type')}")
            print(f"Original Text: {resp.get('original_text')}")
            print(f"Total Client-Server Latency: {elapsed_ms:.2f} ms")
            print("-------------------------\n")
            
    except Exception as e:
        print(f"Benchmark error: {e}")

if __name__ == "__main__":
    asyncio.run(run_benchmark_test())
