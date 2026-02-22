const unzip = require("unzip-crx");

// process.argv[2] is the CRX path from Python
// process.argv[3] is the destination directory
const crxFile = process.argv[2];
const destDir = process.argv[3];

unzip(crxFile, destDir).then(() => {
  console.log("SUCCESS");
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
