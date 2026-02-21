import os
from ollama import Client
import dotenv
dotenv.load_dotenv()
# Set up client for Ollama Cloud
client = Client(
    host="https://ollama.com",
    headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY')}
)

prompt= """
## Clinical History
A 27-year-old nulliparous female came for her first antenatal scan at 32 weeks of gestation with no prior early antenatal scans. She presented with a bilobed abdominal contour seen externally as two distinct bulges with a central vertical depression. No earlier imaging had been done.


## Question
what is the final diagnosis
**Options**:
A. Gravid bicornuate uterus with intercornual communication  
B. Gravid didelphys uterus with partial fusion  
C. Gravid septate uterus with septal placental implantation  
D. Gravid arcuate uterus with exaggerated indentation  
E. Gravid uterus with intrauterine synechiae or band  
only return A, B, C, D, or E, and your reason
"""
response = client.chat(
    model='kimi-k2.5:cloud',
    messages=[
        {'role': 'user', 'content': prompt}
    ]
)

# Access logprobs
print(response)
# for entry in response.get('logprobs', []):
#     print(f"Token: {entry['token']}, LogProb: {entry['logprob']}")