"""Wait quietly for the first event from the seven existing method reviews.

Each child uses the skill's own wait protocol. Return its full output, then
release the other leases so the foreground agent can handle the submission.
"""
from pathlib import Path
import json
import queue
import subprocess
import sys
import threading

ROOT=Path(__file__).resolve().parent
SKILL=Path('C:/Users/36089/.codex/skills/review-html/scripts/review.py')
METHODS=['mle','wmle','mdm','lse','lre','mm','mmle']

def main():
    events=queue.Queue()
    children=[]
    commands={}
    retries={}
    def read_child(method,process):
        output,_=process.communicate()
        events.put((method,process.returncode,output))
    try:
        for method in METHODS:
            folder=ROOT/('method-'+method)
            board=json.loads((folder/'board.json').read_text(encoding='utf8'))
            if board.get('review_complete'):continue
            commands[method]=[sys.executable,str(SKILL),'wait','--root',str(folder),'--revision',str(board['revision'])]
            process=subprocess.Popen(commands[method],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8')
            children.append(process)
            threading.Thread(target=read_child,args=(method,process),daemon=True).start()
        if not children:
            print(json.dumps({'status':'complete'}),flush=True)
            return
        while True:
            method,code,output=events.get()
            # A transient Windows reader can outlast the skill's atomic-rename
            # retry window. Resume only that failed wait, leaving other tasks
            # and all saved feedback intact.
            if code and '[WinError 5]' in output and 'listener.json' in output and retries.get(method,0)<3:
                retries[method]=retries.get(method,0)+1
                process=subprocess.Popen(commands[method],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf8')
                children.append(process)
                threading.Thread(target=read_child,args=(method,process),daemon=True).start()
                continue
            break
        print(json.dumps({'method':method,'exit_code':code,'output':output},ensure_ascii=False),flush=True)
        while not events.empty():
            method,code,output=events.get_nowait()
            print(json.dumps({'method':method,'exit_code':code,'output':output},ensure_ascii=False),flush=True)
    finally:
        for process in children:
            if process.poll() is None:process.terminate()
        for process in children:
            if process.poll() is None:process.wait()

if __name__=='__main__':main()
