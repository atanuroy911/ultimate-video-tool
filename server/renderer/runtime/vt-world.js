/* Reusable 3D sets behind editable SVG characters. Original geometry, no generated scene code.
   A single WebGL context paints each scene's own canvas; scrubbing never creates one context per shot. */
(function(){
  const X=window.VTX;
  X.storyWorld=(d,format)=>{
    const T=window.THREE;if(!T)return null;
    let renderer;
    try {
      renderer=X.worldRenderer||(X.worldRenderer=new T.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true}));
      renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;
      renderer.outputColorSpace=T.SRGBColorSpace;
    } catch(error) { console.warn("3D environment unavailable; using illustrated background",error);return null; }
    const W=format.width,H=format.height,canvas=document.createElement('canvas');
    canvas.width=W;canvas.height=H;canvas.className='cn-world';canvas.dataset.world=d.set;
    const output=canvas.getContext('2d'),scene=new T.Scene();
    const night=d.lighting==='night',sunset=d.lighting==='sunset';
    const sky=night?0x17213e:sunset?0xf4b588:0xbfe4ed;
    scene.background=new T.Color(sky);scene.fog=new T.Fog(sky,19,43);
    const camera=new T.PerspectiveCamera(42,W/H,.1,70);
    scene.add(new T.HemisphereLight(night?0xa5bdff:0xffffff,0x8d826f,night?1.3:2.1));
    const sun=new T.DirectionalLight(sunset?0xffbe7a:night?0x9dbaff:0xfff2d9,night?1.5:3);
    sun.position.set(-8,14,9);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);
    Object.assign(sun.shadow.camera,{left:-18,right:18,top:18,bottom:-18,far:50});sun.shadow.bias=-.0008;scene.add(sun);
    const ink=d.character_style==='ink';
    const material=color=>new T.MeshStandardMaterial({color,roughness:1,metalness:0});
    const mesh=(geometry,color,x,y,z)=>{
      const obj=new T.Mesh(geometry,material(color));obj.position.set(x,y,z);obj.castShadow=true;obj.receiveShadow=true;scene.add(obj);
      if(ink){const lines=new T.LineSegments(new T.EdgesGeometry(geometry,30),new T.LineBasicMaterial({color:0x292439}));obj.add(lines);}
      return obj;
    };
    const box=(x,y,z,w,h,depth,color)=>mesh(new T.BoxGeometry(w,h,depth),color,x,y,z);
    const ball=(x,y,z,r,color)=>mesh(new T.IcosahedronGeometry(r,1),color,x,y,z);
    const tree=(x,z,s=1)=>{mesh(new T.CylinderGeometry(.12*s,.22*s,2*s,7),0x79533d,x,s,z);ball(x,2.5*s,z,1.1*s,0x659562);ball(x+.5*s,2.2*s,z+.2,.7*s,0x83ad6c);};
    const house=(x,z,color,h=3)=>{box(x,h/2,z,3,h,2.6,color);const roof=mesh(new T.ConeGeometry(2.4,1.4,4),0xa65f49,x,h+.65,z);roof.rotation.y=Math.PI/4;
      box(x,.7,z+1.32,.6,1.4,.07,0x66544b);for(const dx of [-.85,.85])box(x+dx,h*.65,z+1.33,.65,.7,.08,night?0xffcb76:0xa5d6db);};
    const indoors=['home','office','classroom','studio','shop'].includes(d.set);
    box(0,-.25,-2,50,.5,55,indoors?0xcbb69a:d.set==='nature'?0x9bbd77:0xe5cba3);
    if(indoors){
      box(0,4,-7,20,8,.35,d.set==='studio'?0x6a7a9b:0xe9dcc5);
      box(-10,4,-1,.3,8,12,0xd5c7b8);box(10,4,-1,.3,8,12,0xd5c7b8);
      for(const x of [-7,7]){box(x,4,-6.75,3,3,.15,0x84735d);box(x,4,-6.6,2.7,2.7,.13,night?0x384773:0xbce6ee);box(x,4,-6.5,.08,2.7,.1,0xfff5e6);}
      if(d.set==='classroom'){box(0,3.7,-6.5,7,3,.2,0xa87d50);box(0,3.7,-6.3,6.6,2.6,.1,0x335b4b);for(const x of [-6,6]){box(x,1.2,-3,2.5,.2,1.6,0xb48253);for(const dx of [-.9,.9])box(x+dx,.6,-3,.15,1.2,.15,0x625950);}}
      if(d.set==='home'){box(0,.8,-4.8,5,1.2,1.8,0x8a9ca7);box(0,1.5,-5.4,5,1.3,.5,0x8a9ca7);box(-3,1,-3,1.3,.2,1.3,0xa17858);tree(6,-4,.8);}
      if(d.set==='office'){for(const x of [-5,5]){box(x,1.4,-4,3,.18,1.6,0xaf9876);box(x,2,-4,.9,.7,.12,0x435164);box(x,1,-4,.2,1,.2,0x615650);}box(0,4.5,-6.5,2,1.4,.15,0x91b1ac);}
      if(d.set==='shop'){for(const x of [-6,6])for(let row=0;row<3;row++){box(x,1+row*1.25,-5,4,.15,1,0x886548);for(let i=0;i<4;i++)box(x-1.4+i*.9,1.4+row*1.25,-5,.5,.65,.6,[0xc78266,0x87a085,0xe6bc73,0x8a96ad][i]);}box(0,.8,-3,3,1.6,1.2,0xb09071);}
      if(d.set==='studio'){box(0,3.4,-6.5,5.5,3,.15,0x34405c);for(const x of [-6,6]){box(x,1.8,-3,.12,3.6,.12,0x414956);ball(x,3.5,-3,.5,0xffdc9e);}}
    } else {
      if(d.set==='street') {box(0,.015,-5,5,.03,35,0x8f9291);for(let z=-18;z<10;z+=4)box(0,.04,z,.12,.025,1.8,0xf8ebc5);for(let i=0;i<5;i++){house(-6,-3-i*5,[0xd8b08a,0xc88b78,0x9caea7][i%3],3+i%2);house(6,-5-i*5,[0xa7b5bf,0xd7bc8f,0xb9a5a4][i%3],3+(i+1)%3);}}
      if(d.set==='village'){for(const [x,z,c] of [[-5,-5,0xe1ba8a],[5,-7,0xd79778],[0,-13,0xdac7a2]])house(x,z,c);tree(-8,-3);tree(8,-4,1.2);}
      if(d.set==='market'){for(const x of [-5,5]){box(x,1,-4,3.3,1.6,1.5,0xbc8b56);box(x,3,-4,3.8,.18,2,0xf4dfb4);for(let i=0;i<6;i++)box(x-1.5+i*.6,2.85,-2.95,.6,.5,.1,i%2?0xf0d5a2:0xbb6a54);for(let i=0;i<5;i++)ball(x-1.2+i*.6,1.95,-3.6,.25,i%2?0xddaf43:0xad5c43);}house(0,-11,0xd7bd9c);}
      if(d.set==='nature'){for(let i=0;i<12;i++)tree((i%2?-1:1)*(4+i%4),-3-i*2,1+(i%3)*.2);for(const x of [-8,8,0])ball(x,2,-22,6,0x83a47c);}
      if(d.set==='plain'){for(const [x,z,r] of [[-6,-5,2],[6,-8,3],[0,-15,4]])ball(x,r/2,z,r,0xb3c7bd);}
    }
    const draw=(u=0)=>{
      const move=d.camera||'push',distance=move==='pull'?13+u*1.3:move==='push'?14.3-u*1.3:14;
      camera.position.set(move==='pan'?-1.4+u*2.8:0,5.2,distance);camera.lookAt(move==='pan'?.4-u*.8:0,2,-3);
      renderer.setSize(W,H,false);renderer.render(scene,camera);output.drawImage(renderer.domElement,0,0,W,H);
    };
    draw();
    (X.worldDisposers||(X.worldDisposers=[])).push(()=>scene.traverse(o=>{o.geometry?.dispose();if(o.material)for(const m of [o.material].flat())m.dispose();}));
    return {canvas,animate(tl,start,end){const clock={};Object.defineProperty(clock,'progress',{get:()=>0,set:draw});tl.fromTo(clock,{progress:0},{progress:1,duration:Math.max(.01,end-start),ease:'none'},start);}};
  };
})();
