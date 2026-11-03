"""Reusable, editable arrangements adapted to our canonical HyperFrames components."""
TEMPLATES = [
    {"id":"typewriter-title","name":"Typewriter title","type":"title","category":"Animated text","patch":{"text":"One small change","entrance":"typewriter-moves"}},
    {"id":"flying-title","name":"Flying words","type":"title","category":"Animated text","patch":{"text":"Make your next move","entrance":"flying-words"}},
    {"id":"word-by-word","name":"Word by word","type":"title","category":"Animated text","patch":{"text":"One step at a time","entrance":"type-rhythm-sync"}},
    {"id":"neon-title","name":"Neon lettering","type":"title","category":"Scene lettering","patch":{"text":"Your bright idea","text_style":"neon","entrance":"neon-frame-orbit-drop"}},
    {"id":"chalk-title","name":"Chalkboard text","type":"title","category":"Scene lettering","patch":{"text":"Your key lesson","text_style":"chalk","entrance":"typewriter-moves"}},
    {"id":"paint-title","name":"Painted lettering","type":"title","category":"Scene lettering","patch":{"text":"Your words here","text_style":"paint","entrance":"draw-svg-trace"}},
    {"id":"paper-title","name":"Paper cutout title","type":"title","category":"Scene lettering","patch":{"text":"A new chapter","text_style":"paper","entrance":"paper-title-card"}},
    {"id":"outline-title","name":"Outline reveal","type":"title","category":"Animated text","patch":{"text":"Your next idea","text_style":"outline","entrance":"outline-word-fill"}},
    {"id":"marker-title","name":"Marker highlight","type":"title","category":"Animated text","patch":{"text":"Remember this","text_style":"marker","entrance":"marker-underline-title"}},
    *[{"id":f"{style}-story","name":f"{style.capitalize()} story scene","type":"cartoon","category":"Story templates","patch":{"framing":"scene","world":"3d","character_style":style,"set":"street","camera":"push","cast":[{"who":"teacher","name":"Sam","x":.35,"pose":"wave"},{"who":"robot","name":"Pip","x":.7,"pose":"think"}],"bubble":"","props":[]}} for style in ('classic','ink','paper')],
    {"id":"product-reveal","name":"Product reveal","type":"media_frame","category":"Motion graphics","patch":{"frame":"plain","caption":"","entrance":"spotlight-sweep-moves"}},
    {"id":"app-demo","name":"App demonstration","type":"device","category":"Motion graphics","patch":{"kind":"phone","caption":"Your app","entrance":"card-flip-reveal"}},
    {"id":"drawn-process","name":"Draw a process","type":"flow","category":"Motion graphics","patch":{"entrance":"draw-svg-trace"}},
    {"id":"stat-reveal","name":"Statistic reveal","type":"big_number","category":"Motion graphics","patch":{"entrance":"countdown-arc-scatter"}},
]


def templates(components):
    by_type={c['type']:c for c in components}
    return [{**by_type[t['type']], 'variant':t['id'], 'name':t['name'], 'category':t['category'],
             'starter':{**by_type[t['type']]['starter'],**t['patch']},
             'use_when':f"{t['name']}. Editable content, appearance and motion; replace starter text with your own facts."} for t in TEMPLATES]
