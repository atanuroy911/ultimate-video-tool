/* Read-only renderer fixture for testing the exact native manager HTML in a browser. */
const http=require('http'),fs=require('fs'),path=require('path');
const base='http://127.0.0.1:8790';
const adapter=`window.serverManager={state:async()=>({running:true,url:${JSON.stringify(base)},computer:'Local server',addresses:[${JSON.stringify(base)}],autostart:false,tray:true,progress:{}}),act:async action=>{if(action==='engine-settings')return {url:${JSON.stringify(base+'/manage?embedded=1')}};if(action==='open-log')return {log:'Server is running. Engine settings are contained in this app.'};throw new Error('This read-only preview does not change server state.');},onProgress:()=>{}};`;
http.createServer((req,res)=>{
 if(req.url==='/fixture-adapter.js'){res.setHeader('Content-Type','text/javascript');res.end(adapter);return;}
 const name=req.url==='/'?'server-manager.html':req.url.slice(1);
 if(!['server-manager.html','server-manager-ui.js','server-icon.png'].includes(name)){res.writeHead(404);res.end();return;}
 let data=fs.readFileSync(path.join(__dirname,name));
 if(name.endsWith('.html'))data=String(data).replace('<script src="server-manager-ui.js">','<script src="/fixture-adapter.js"></script><script src="server-manager-ui.js">');
 res.setHeader('Content-Type',name.endsWith('.html')?'text/html':name.endsWith('.js')?'text/javascript':'image/png');res.end(data);
}).listen(Number(process.env.UVT_PREVIEW_PORT||9174),'127.0.0.1',()=>console.log('Contained manager preview is ready.'));
