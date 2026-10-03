import Foundation

private protocol Source<Element> {
    associatedtype Element
    var element: Element { get }
}
private class Base<Value: Hashable> {
    let value: Value
    init(_ value: Value) { self.value = value }
}
private final class Concrete<Value: Hashable>: Base<Value>, Source {
    var element: Value { value }
}
private class UnconstrainedBase<Value> {
    let value: Value
    init(_ value: Value) { self.value = value }
}
private final class UnconstrainedConcrete<Value>: UnconstrainedBase<Value>, Source {
    var element: Value { value }
}

private struct Result: Codable {
    let mode: String
    let value: Int?
}

let mode = CommandLine.arguments.dropFirst().first ?? "constrained"
let value: Int?
switch mode {
case "constrained":
    let erased: Any = Concrete(42)
    value = (erased as? any Base<Int> & Source<Int>)?.element
case "unconstrained":
    let erased: Any = UnconstrainedConcrete(42)
    value = (erased as? any UnconstrainedBase<Int> & Source<Int>)?.element
case "protocol-only":
    let erased: Any = Concrete(42)
    value = (erased as? any Source<Int>)?.element
case "superclass-only":
    let erased: Any = Concrete(42)
    value = (erased as? Base<Int>)?.value
default:
    FileHandle.standardError.write(Data("Use constrained, unconstrained, protocol-only, or superclass-only.\n".utf8))
    exit(64)
}
print(String(decoding: try JSONEncoder().encode(Result(mode: mode, value: value)), as: UTF8.self))
