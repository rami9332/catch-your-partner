import CoreLocation
import Foundation
import UIKit

final class MapMeetingCoordinator {
    struct CandidateLocation {
        let latitude: Double
        let longitude: Double

        var coordinate: CLLocationCoordinate2D {
            CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
        }
    }

    struct MeetingPoint {
        let name: String
        let latitude: Double
        let longitude: Double

        var coordinate: CLLocationCoordinate2D {
            CLLocationCoordinate2D(latitude: latitude, longitude: longitude)
        }

        var jsonString: String {
            """
            {"name":"\(name.replacingOccurrences(of: "\"", with: "\\\""))","lat":\(latitude),"lng":\(longitude)}
            """
        }
    }

    struct AcceptanceStatus {
        let youAccepted: Bool
        let otherAccepted: Bool
        let fullyAccepted: Bool
    }

    struct ArrivalStatus {
        let youArrived: Bool
        let otherArrived: Bool
        let bothArrived: Bool
    }

    struct OkStatus {
        let youOk: Bool
        let otherOk: Bool
        let bothOk: Bool
        let chatUnlocked: Bool
    }

    struct MeetingActionContext {
        let meetingId: Int
        let backendOrigin: String
        let authToken: String
    }

    struct MapResult {
        struct ServerMeetingPayload {
            let id: Int
            let spotName: String
            let spotLat: Double
            let spotLng: Double
            let status: String
            let acceptedBy: [String]
            let arrivedBy: [String]
            let okBy: [String]
            let fullyAccepted: Bool
            let bothArrived: Bool
            let bothOk: Bool
            let chatUnlocked: Bool

            var jsonString: String {
                let acceptedByJSON = acceptedBy.map { "\"\($0.replacingOccurrences(of: "\"", with: "\\\""))\"" }.joined(separator: ",")
                let arrivedByJSON = arrivedBy.map { "\"\($0.replacingOccurrences(of: "\"", with: "\\\""))\"" }.joined(separator: ",")
                let okByJSON = okBy.map { "\"\($0.replacingOccurrences(of: "\"", with: "\\\""))\"" }.joined(separator: ",")
                return """
                {"id":\(id),"spot_name":"\(spotName.replacingOccurrences(of: "\"", with: "\\\""))","spot_lat":\(spotLat),"spot_lng":\(spotLng),"status":"\(status.replacingOccurrences(of: "\"", with: "\\\""))","accepted_by":[\(acceptedByJSON)],"arrived_by":[\(arrivedByJSON)],"ok_by":[\(okByJSON)],"fully_accepted":\(fullyAccepted),"both_arrived":\(bothArrived),"both_ok":\(bothOk),"chat_unlocked":\(chatUnlocked)}
                """
            }
        }

        struct RouteMeta {
            let distanceMeters: Double
            let expectedTravelTimeSeconds: Double

            var jsonString: String {
                """
                {"distanceMeters":\(distanceMeters),"expectedTravelTimeSeconds":\(expectedTravelTimeSeconds)}
                """
            }
        }

        let type = "meetingMapResult"
        let location: CLLocationCoordinate2D?
        let accuracy: CLLocationAccuracy?
        let meetingPoint: MeetingPoint?
        let routeMeta: RouteMeta?
        let serverMeeting: ServerMeetingPayload?
        let openChat: Bool
        let errorStatus: String?

        var jsonString: String {
            let locationJSON: String
            if let location {
                let accuracyValue = accuracy.map { String(format: "%.1f", $0) } ?? "null"
                locationJSON = """
                {"lat":\(location.latitude),"lng":\(location.longitude),"accuracy":\(accuracyValue)}
                """
            } else {
                locationJSON = "null"
            }
            let meetingPointJSON = meetingPoint?.jsonString ?? "null"
            let routeMetaJSON = routeMeta?.jsonString ?? "null"
            let serverMeetingJSON = serverMeeting?.jsonString ?? "null"
            let openChatJSON = openChat ? "true" : "false"
            let error = errorStatus.map { "\"\($0)\"" } ?? "null"
            return """
            {"type":"\(type)","location":\(locationJSON),"meetingPoint":\(meetingPointJSON),"routeMeta":\(routeMetaJSON),"serverMeeting":\(serverMeetingJSON),"openChat":\(openChatJSON),"errorStatus":\(error)}
            """
        }
    }

    private var isPresenting = false

    func openMap(
        meetingPoint: MeetingPoint?,
        candidateLocation: CandidateLocation?,
        acceptanceStatus: AcceptanceStatus?,
        arrivalStatus: ArrivalStatus?,
        okStatus: OkStatus?,
        meetingContext: MeetingActionContext?,
        completion: @escaping (MapResult) -> Void
    ) {
        DispatchQueue.main.async {
            guard !self.isPresenting else {
                completion(MapResult(location: nil, accuracy: nil, meetingPoint: meetingPoint, routeMeta: nil, serverMeeting: nil, openChat: false, errorStatus: "map_unavailable"))
                return
            }

            guard let presenter = Self.topViewController() else {
                completion(MapResult(location: nil, accuracy: nil, meetingPoint: meetingPoint, routeMeta: nil, serverMeeting: nil, openChat: false, errorStatus: "map_unavailable"))
                return
            }

            self.isPresenting = true
            let controller = MapMeetingViewController(
                meetingPoint: meetingPoint,
                candidateLocation: candidateLocation,
                acceptanceStatus: acceptanceStatus,
                arrivalStatus: arrivalStatus,
                okStatus: okStatus,
                meetingContext: meetingContext
            ) { [weak self] result in
                self?.isPresenting = false
                completion(result)
            }
            controller.modalPresentationStyle = .fullScreen
            presenter.present(controller, animated: true)
        }
    }

    private static func topViewController(
        base: UIViewController? = UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)?
            .rootViewController
    ) -> UIViewController? {
        if let navigation = base as? UINavigationController {
            return topViewController(base: navigation.visibleViewController)
        }
        if let tab = base as? UITabBarController {
            return topViewController(base: tab.selectedViewController)
        }
        if let presented = base?.presentedViewController {
            return topViewController(base: presented)
        }
        return base
    }
}
