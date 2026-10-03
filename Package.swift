// swift-tools-version: 6.3
import PackageDescription

let package = Package(
    name: "SwiftSuperclassExistentialRepro",
    platforms: [.macOS(.v15)],
    products: [
        .executable(name: "LayoutProbe", targets: ["LayoutProbe"]),
        .executable(name: "CastProbe", targets: ["CastProbe"]),
        .executable(name: "RuntimeProbe", targets: ["RuntimeProbe"]),
    ],
    targets: [
        .executableTarget(name: "LayoutProbe"),
        .executableTarget(name: "CastProbe"),
        .executableTarget(name: "RuntimeProbe"),
    ]
)
