const http=require('http'),fs=require('fs');
http.createServer((req,res)=>{
  let b='IR-BUILDPACK-RUNTIME\n';
  try{b+=fs.readFileSync('build-report.txt','utf8');}catch(e){b+='no report: '+e.message;}
  res.writeHead(200,{'content-type':'text/plain'});res.end(b);
}).listen(process.env.PORT||8080,()=>console.log('up'));
