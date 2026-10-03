import Foundation

private class Base<Value: Hashable> {}
private class UnconstrainedBase<Value> {}
private protocol Source<Element>: AnyObject { associatedtype Element }

private struct Layout: Codable {
    let size: Int
    let stride: Int
    let alignment: Int
}

@inline(never) private func genericLayout<T>(_: T.Type) -> Layout {
    Layout(size: MemoryLayout<T>.size, stride: MemoryLayout<T>.stride,
           alignment: MemoryLayout<T>.alignment)
}

private struct Result: Codable {
    let mode: String
    let concrete: Layout
    let generic: Layout
}

let mode = CommandLine.arguments.dropFirst().first ?? "constrained"
let type: Any.Type
private let concrete: Layout
switch mode {
case "constrained":
    type = (any Base<Int> & Source<Int>).self
    concrete = Layout(size: MemoryLayout<any Base<Int> & Source<Int>>.size,
                      stride: MemoryLayout<any Base<Int> & Source<Int>>.stride,
                      alignment: MemoryLayout<any Base<Int> & Source<Int>>.alignment)
case "unconstrained":
    type = (any UnconstrainedBase<Int> & Source<Int>).self
    concrete = Layout(size: MemoryLayout<any UnconstrainedBase<Int> & Source<Int>>.size,
                      stride: MemoryLayout<any UnconstrainedBase<Int> & Source<Int>>.stride,
                      alignment: MemoryLayout<any UnconstrainedBase<Int> & Source<Int>>.alignment)
default:
    FileHandle.standardError.write(Data("Use constrained or unconstrained.\n".utf8))
    exit(64)
}
private let result = Result(mode: mode, concrete: concrete, generic: genericLayout(type))
print(String(decoding: try JSONEncoder().encode(result), as: UTF8.self))
