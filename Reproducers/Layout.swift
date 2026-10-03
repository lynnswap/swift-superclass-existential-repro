private class Base<Value: Hashable> {}
private protocol Source<Element>: AnyObject { associatedtype Element }

@inline(never) private func genericSize<T>(_: T.Type) -> Int {
    MemoryLayout<T>.size
}

let type: Any.Type = (any Base<Int> & Source<Int>).self
print("static", MemoryLayout<any Base<Int> & Source<Int>>.size)
print("generic", genericSize(type))
