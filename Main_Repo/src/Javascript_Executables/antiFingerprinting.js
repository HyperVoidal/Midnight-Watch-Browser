//Adjust what the reported screensize parameters are
(() => {

const orig =
HTMLCanvasElement.prototype.toDataURL;

HTMLCanvasElement.prototype.toDataURL =
function(){

    const ctx=this.getContext("2d");

    if(ctx){

        const img=
        ctx.getImageData(
            0,0,
            this.width,
            this.height
        );

        for(let i=0;i<img.data.length;i+=4){

            img.data[i]+=1;
            img.data[i+1]-=1;
        }

        ctx.putImageData(img,0,0);
    }

    return orig.apply(this,arguments);
};

})();


//Return information about the browser that is as generic as possible
const getParameter =
WebGLRenderingContext.prototype.getParameter;

WebGLRenderingContext.prototype.getParameter =
function(param){

    if(param===37445)
        return "Generic GPU";

    if(param===37446)
        return "Generic Renderer";

    return getParameter.apply(
        this,
        arguments
    );
};


//hardwareConcurrency is number of threads of the cpu. Return a given value for obfuscation
Object.defineProperty(
    navigator,
    "hardwareConcurrency",
{
    get:()=>4
});


//obfuscate memory
Object.defineProperty(
    navigator,
    "deviceMemory",
{
    get:()=>8
});


//obfuscate timings
const orig=performance.now;

performance.now=()=>
Math.floor(orig()/100)*100;

