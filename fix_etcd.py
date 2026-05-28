with open('docker-compose.yml', encoding='utf-8') as f:
    c = f.read()

c = c.replace(
    'image: bitnami/etcd:latest',
    'image: gcr.io/etcd-development/etcd:v3.5.17'
)

old_hc = '["CMD", "etcdctl", "endpoint", "health"]'
new_hc = '["CMD", "etcdctl", "--endpoints=http://localhost:2379", "endpoint", "health"]'
c = c.replace(old_hc, new_hc)

# Also remove the obsolete version: field if still present
lines = [l for l in c.splitlines(keepends=True) if not l.startswith('version:')]
c = ''.join(lines)

with open('docker-compose.yml', 'w', encoding='utf-8', newline='\n') as f:
    f.write(c)

print('Done')
