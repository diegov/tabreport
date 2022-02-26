var { createCanvas, Image } = require('canvas');
var Two = require('two.js');

var fs = require('fs');
var path = require('path');

var width = 500;
var height = 500;

function place_x(x) {
  return x + (width / 2);
}

function place_y(y) {
  return y + (height / 2);
}

var canvas = createCanvas(width, height, type='svg');
Two.Utils.shim(canvas, Image);

var two = new Two({
  width: width,
  height: height,
  domElement: canvas
});

var offset_x = width / 20;
var offset_y = offset_x;

var size_x = width - (2 * offset_x);
var size_y = height - (2 * offset_y);

var rect = two.makeRoundedRectangle(width / 2,
                                    height / 2,
                                    size_x,
                                    size_y,
                                    size_x / 3);
rect.fill = 'rgb(92, 147, 119)';
rect.noStroke();

var r_width = width / 2;
var r_height = height / 2;
rect = two.makeRectangle(width / 3 + r_width / 2,
                         height / 3 + r_height / 2,
                         r_width,
                         r_height);
rect.fill = 'rgb(104, 157, 105)';
rect.noStroke();

two.render();

var settings = { };

var outputPath = process.argv[2];

fs.writeFileSync(path.resolve(outputPath), canvas.toBuffer('image/svg+xml', settings));

process.exit();
