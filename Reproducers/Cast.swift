protocol Source<Element> {
    associatedtype Element
    var element: Element { get }
}
class Base<Value: Hashable> {
    let value: Value
    init(_ value: Value) { self.value = value }
}
final class Concrete<Value: Hashable>: Base<Value>, Source {
    var element: Value { value }
}

let erased: Any = Concrete(42)
if let value = erased as? any Base<Int> & Source<Int> {
    print(value.element)
} else {
    print("cast failed")
}
