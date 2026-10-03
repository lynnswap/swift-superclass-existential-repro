import Foundation
import MachO

struct RuntimeInfo: Codable {
    let os: String
    let architecture: String
    let swiftCoreImages: [String]
}

#if arch(arm64)
let architecture = "arm64"
#elseif arch(x86_64)
let architecture = "x86_64"
#else
let architecture = "other"
#endif

let paths = (0..<_dyld_image_count()).compactMap { index -> String? in
    guard let name = _dyld_get_image_name(index) else { return nil }
    let path = String(cString: name)
    return path.hasSuffix("/libswiftCore.dylib") ? path : nil
}
let result = RuntimeInfo(os: ProcessInfo.processInfo.operatingSystemVersionString,
                         architecture: architecture, swiftCoreImages: paths)
print(String(decoding: try JSONEncoder().encode(result), as: UTF8.self))
