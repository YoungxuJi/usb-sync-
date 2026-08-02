class MenuSystem:
    def __init__(self):
        self.running = True
    
    def display_menu(self, title, options):
        """
        显示菜单
        :param title: 菜本标题
        :param options: 选项列表，每个选项为字典，包含 'description' 键
        """
        print("\n" + "="*50)
        print(title)
        print("="*50)
        for index, option in enumerate(options):
            print(f"{index+1}. {option['description']}")
        # print("="*50)
    
    def get_user_choice(self, options_count):
        """
        获取用户选择
        :param options_count: 选项数量
        :return: 用户选择的索引，-1表示退出
        """
        while True:
            try:
                user_input = input("请输入选项编号（输入 'q' 退出）: ").strip().lower()
                if user_input == 'q':
                    return -1
                
                choice = int(user_input)
                if 1 <= choice < options_count+1:
                    return choice-1
                else:
                    print(f"请输入 1 到 {options_count} 之间的数字。")
            except ValueError:
                print("请输入有效的数字或 'q' 退出。")
    
    def run_menu(self, title, options):
        """
        运行菜单循环
        :param title: 菜单标题
        :param options: 选项列表，每个选项应包含 'description' 和 'callback' 键
        """
        while self.running:
            self.display_menu(title, options)
            choice = self.get_user_choice(len(options))
            
            if choice == -1:  # 用户选择退出
                print("程序退出。")
                self.running = False
                return
            
            # 执行选中选项的回调函数
            if 'callback' in options[choice] and options[choice]['callback']:
                if 'args' in options[choice] and options[choice]['args']:
                    next_menu = options[choice]['callback'](*options[choice]['args'])
                else:
                    next_menu = options[choice]['callback']()
                # 如果回调函数返回了下一个菜单，则运行该菜单
                if next_menu:
                    next_menu_title, next_menu_options = next_menu
                    self.run_menu(next_menu_title, next_menu_options)
                    # 返回当前菜单后继续显示当前菜单
                    continue
            else:
                print("该选项没有定义功能。")
            
            input("\n按回车键继续...")
