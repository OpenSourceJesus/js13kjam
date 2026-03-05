import time, json, socket, select

HEADER_LENGTH = 10
IP = '0.0.0.0'
PORT = 12345

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((IP, PORT))
server_socket.listen()

sockets_list = [server_socket]
clients = {}
player_states = {}

print(f'Listening for connections on {IP}:{PORT}...')

def receive_message(client_socket):
	try:
		message_header = client_socket.recv(HEADER_LENGTH)
		if not len(message_header):
			return False
		message_length = int(message_header.decode('utf-8').strip())
		return {'header': message_header, 'data': client_socket.recv(message_length)}
	except:
		return False

while True:
	read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list)
	for notified_socket in read_sockets:
		if notified_socket == server_socket:
			client_socket, client_address = server_socket.accept()
			client_id = f'player_{int(time.time())}'
			sockets_list.append(client_socket)
			clients[client_socket] = client_id
			player_states[client_id] = {'pos': [0, 0]}
			print(f'Accepted new connection from {client_address[0]}:{client_address[1]} as {client_id}')
		else:
			message = receive_message(notified_socket)
			if message is False:
				client_id = clients[notified_socket]
				print(f'Closed connection from {client_id}')
				sockets_list.remove(notified_socket)
				del clients[notified_socket]
				del player_states[client_id]
				continue
			client_id = clients[notified_socket]
			data = json.loads(message['data'].decode('utf-8'))
			player_states[client_id] = data
			print(f'Received from {client_id}: {data}')
	if player_states:
		state_data = json.dumps(player_states).encode('utf-8')
		state_header = f'{len(state_data):<{HEADER_LENGTH}}'.encode('utf-8')
		for client_socket in clients:
			client_socket.send(state_header + state_data)
	for notified_socket in exception_sockets:
		sockets_list.remove(notified_socket)
		del clients[notified_socket]