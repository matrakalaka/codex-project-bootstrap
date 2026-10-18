import Foundation
import Security

struct Request: Codable { let command: String; let service: String; let account: String; let value: String? }
struct Response: Codable { let ok: Bool; let value: String?; let error: String? }

func fail(_ status: OSStatus) -> Never {
    let response = Response(ok: false, value: nil, error: "Security.framework status \(status)")
    let data = try! JSONEncoder().encode(response)
    FileHandle.standardError.write(data)
    exit(1)
}

let input = FileHandle.standardInput.readDataToEndOfFile()
guard let request = try? JSONDecoder().decode(Request.self, from: input), !request.service.isEmpty, !request.account.isEmpty else { fail(errSecParam) }
let identity: [CFString: Any] = [kSecClass: kSecClassGenericPassword, kSecAttrService: request.service as CFString, kSecAttrAccount: request.account as CFString]

switch request.command {
case "put":
    guard let encoded = request.value, let data = Data(base64Encoded: encoded) else { fail(errSecParam) }
    // kSecAttrAccessibleThisDeviceOnly is an iOS attribute and returns
    // errSecParam on macOS. macOS Keychain access is governed by the item ACL
    // and application code-signing boundary instead.
    var item = identity; item[kSecValueData] = data
    var status = SecItemAdd(item as CFDictionary, nil)
    if status == errSecDuplicateItem {
        let update: [CFString: Any] = [kSecValueData: data]
        status = SecItemUpdate(identity as CFDictionary, update as CFDictionary)
    }
    if status != errSecSuccess { fail(status) }
case "get":
    var query = identity; query[kSecReturnData] = true; query[kSecMatchLimit] = kSecMatchLimitOne
    var result: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &result)
    guard status == errSecSuccess, let data = result as? Data else { fail(status) }
    let response = Response(ok: true, value: data.base64EncodedString(), error: nil)
    FileHandle.standardOutput.write(try! JSONEncoder().encode(response))
case "delete":
    let status = SecItemDelete(identity as CFDictionary)
    if status != errSecSuccess && status != errSecItemNotFound { fail(status) }
default: fail(errSecParam)
}
