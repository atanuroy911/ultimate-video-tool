export type Account = {id:string;platform:string;name:string;handle:string;active:number};
export type Group = {id:string;name:string;accounts:Account[]};
export const platformNames:Record<string,string>={youtube:"YouTube",instagram:"Instagram",facebook:"Facebook",tiktok:"TikTok",mock:"Practice channel"};
export const platformMark:Record<string,string>={youtube:"▶",instagram:"◎",facebook:"f",tiktok:"♪",mock:"✓"};
