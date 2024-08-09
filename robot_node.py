import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import sys

class RobotNode(Node):
    def __init__(self, robot_id):
        super().__init__('robot_' + robot_id)
        self.robot_id = robot_id
        self.publisher = self.create_publisher(String, 'robot_topic', 10)
        self.subscription = self.create_subscription(
            String,
            'robot_topic',
            self.listener_callback,
            10
        )
        self.subscription  # prevent unused variable warning
        self.timer = self.create_timer(1.0, self.timer_callback)

    def listener_callback(self, msg):
        if f'{self.robot_id}' not in msg.data:
            self.get_logger().info(f'Received: "{msg.data}"')

    def timer_callback(self):
        msg = String()
        msg.data = f'data from {self.robot_id}'
        self.publisher.publish(msg)
        self.get_logger().info(f'Sent: "{msg.data}"')

def main(args=None):
    rclpy.init(args=args)
    robot_id = sys.argv[1]
    node = RobotNode(robot_id)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
