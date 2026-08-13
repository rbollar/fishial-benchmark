// Vision-crop harness: mirrors BulkCritterIDService's pre-screen —
// VNGenerateAttentionBasedSaliencyImageRequest, first salient object,
// expanded 12%, cropped. No salient object => whole frame (recorded).
import Foundation
import Vision
import ImageIO
import UniformTypeIdentifiers

let srcDir = URL(fileURLWithPath: CommandLine.arguments[1])
let dstDir = URL(fileURLWithPath: CommandLine.arguments[2])
try? FileManager.default.createDirectory(at: dstDir, withIntermediateDirectories: true)
var log = "image,cropped,x,y,w,h\n"

let files = try FileManager.default.contentsOfDirectory(at: srcDir, includingPropertiesForKeys: nil)
    .sorted { $0.lastPathComponent < $1.lastPathComponent }
for url in files {
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let img = CGImageSourceCreateImageAtIndex(src, 0, nil) else { continue }
    let req = VNGenerateAttentionBasedSaliencyImageRequest()
    try? VNImageRequestHandler(cgImage: img).perform([req])
    var out = img
    var cropped = false
    var rect = CGRect.zero
    if let salient = req.results?.first?.salientObjects?.first {
        let bb = salient.boundingBox   // normalized, bottom-left origin
        let W = CGFloat(img.width), H = CGFloat(img.height)
        let pad: CGFloat = 0.12
        let w = bb.width * (1 + 2 * pad) * W
        let h = bb.height * (1 + 2 * pad) * H
        let x = max(0, (bb.minX - bb.width * pad) * W)
        let y = max(0, (1 - bb.maxY - bb.height * pad) * H)   // flip to top-left
        rect = CGRect(x: x, y: y, width: min(w, W - x), height: min(h, H - y))
        if rect.width > 40, rect.height > 40, let c = img.cropping(to: rect) {
            out = c
            cropped = true
        }
    }
    let dst = dstDir.appendingPathComponent(url.deletingPathExtension().lastPathComponent + ".jpg")
    if let d = CGImageDestinationCreateWithURL(dst as CFURL, UTType.jpeg.identifier as CFString, 1, nil) {
        CGImageDestinationAddImage(d, out, [kCGImageDestinationLossyCompressionQuality: 0.92] as CFDictionary)
        CGImageDestinationFinalize(d)
    }
    log += "\(url.lastPathComponent),\(cropped),\(Int(rect.minX)),\(Int(rect.minY)),\(Int(rect.width)),\(Int(rect.height))\n"
}
try log.write(to: dstDir.appendingPathComponent("crops.csv"), atomically: true, encoding: .utf8)
print("VISION_CROP_DONE \(files.count)")
