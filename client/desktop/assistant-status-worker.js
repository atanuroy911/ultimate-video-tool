const {parentPort,workerData}=require('worker_threads');
try {parentPort.postMessage(require(workerData.kind==='codex'?'./codex-runner':'./director-runner').status());}
catch(e){parentPort.postMessage({found:false,logged_in:false,version:'',reason:e.message});}
