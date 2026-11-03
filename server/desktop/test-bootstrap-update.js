const assert=require('assert'),fs=require('fs'),path=require('path'),os=require('os');
const B=require('./bootstrap');
const parent=fs.realpathSync(os.tmpdir());const root=fs.mkdtempSync(path.join(parent,'vt-update-check-'));
try{
 const source=path.join(root,'source'),home=path.join(root,'home');fs.mkdirSync(path.join(source,'vt'),{recursive:true});fs.writeFileSync(path.join(source,'vt','server.py'),'old code');
 let layout=B.layout(home,source,'1.0.0');fs.mkdirSync(path.dirname(layout.python),{recursive:true});fs.writeFileSync(layout.python,'test interpreter');fs.mkdirSync(path.dirname(layout.stamp),{recursive:true});
 fs.writeFileSync(layout.stamp,JSON.stringify({version:'1.0.0',done:true}));assert.equal(B.isReady(layout),false);
 fs.writeFileSync(layout.stamp,JSON.stringify({version:'1.0.0',done:true,source_hash:layout.sourceHash}));assert.equal(B.isReady(layout),true);
 fs.writeFileSync(path.join(source,'vt','server.py'),'updated code');layout=B.layout(home,source,'1.0.0');assert.equal(B.isReady(layout),false);
 console.log('Server bootstrap refreshes changed code even when the product version is unchanged.');
}finally{if(!path.resolve(root).startsWith(parent+path.sep))throw new Error('Unsafe test cleanup path');fs.rmSync(root,{recursive:true,force:true});}
