from jinja2 import Environment, FileSystemLoader

template_dir = './'
def create_jinja2_env():
    """创建 Jinja2 环境"""
    env = Environment(loader=FileSystemLoader(template_dir))
    return env

jinja_env = create_jinja2_env()

def test_template():
    template = jinja_env.get_template('test_template.html')
    result = template.render()
    with open('result.html', 'w') as f:
        f.write(result)

if __name__ == '__main__':
    test_template()