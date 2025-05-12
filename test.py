import streamlit as st
import pandas as pd
import requests
from streamlit.components.v1 import html
import os
# 百度地图配置
SERVER_AK = "j44ZAQiQcNRl4IfSAA2DqTeWyWCQkjKg"  # 服务端类型应用
BROWSER_AK = "F2h8URNdw483r3LQXY7xE1Q8hknD1dRy"  # 浏览器端类型应用
DIRECTION_API_URL = "https://api.map.baidu.com/direction/v2/driving"
# 检查密码是否正确
# if "PASSWORD" not in st.secrets:
#     st.error("❌ Secrets 未正确配置，请检查云端设置！")
#     st.stop()
#
# password = st.text_input("请输入密码", type="password")
# correct_password = st.secrets["PASSWORD"]
#
# if password != correct_password:
#     st.error("密码错误")
#     st.stop()
#
# st.success("✅ 密码正确！")
# # 以下是应用的正式内容
# st.write("欢迎访问受保护的应用！")
def get_driving_route(origin_lng, origin_lat, dest_lng, dest_lat):
    """获取驾驶路径详细信息"""
    params = {
        "origin": f"{origin_lat},{origin_lng}",
        "destination": f"{dest_lat},{dest_lng}",
        "ak": SERVER_AK,
        "coord_type": "bd09ll",
        "ret_coordtype": "bd09ll",
        "output": "json"
    }
    try:
        response = requests.get(DIRECTION_API_URL, params=params)
        data = response.json()
        if data.get('status') == 0:
            route = data['result']['routes'][0]
            path_points = [
                [float(lng), float(lat)]
                for step in route['steps']
                for point in step['path'].split(';')
                if len(point.split(',')) == 2  # 添加容错处理
                for lng, lat in [point.split(',')]  # 直接解包
            ]
            return {
                "distance": route["distance"],
                "duration": route["duration"],
                "processed_path": path_points
            }
        st.error(f"路径请求失败: {data.get('message')}")
    except Exception as e:
        st.error(f"API请求异常: {str(e)}")
    return None


def generate_baidu_map_html(store_list, path_points):
    """生成地图HTML（修复路径绘制）"""

    # 确保路径点不为空
    if not path_points:
        return "<div>无路径数据</div>"

    # 生成路径点JS代码
    path_js = ",\n".join([f"new BMap.Point({p[0]}, {p[1]})" for p in path_points])

    # 生成标记点JS代码
    markers_js = "\n".join([
        f"""
        var marker{idx} = new BMap.Marker(new BMap.Point({store['longitude']}, {store['latitude']}));
        map.addOverlay(marker{idx});
        var label{idx} = new BMap.Label("{idx + 1}-{store['门店名称']}", {{offset: new BMap.Size(20, -10)}});
        marker{idx}.setLabel(label{idx});
        """
        # 修改3：直接使用传入的顺序生成序号
        for idx, store in enumerate(store_list)
    ])

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <script src="https://api.map.baidu.com/api?v=3.0&ak={BROWSER_AK}"></script>
        <style>
            #map-container {{ height: 500px; width: 100%; border: 2px solid #eee; }}
        </style>
    </head>
    <body>
        <div id="map-container"></div>
        <script>
            // 确保地图API加载完成
            function initialize() {{
                var map = new BMap.Map("map-container");
                map.centerAndZoom(new BMap.Point({path_points[0][0]}, {path_points[0][1]}), 13);
                map.enableScrollWheelZoom(true);

                // 绘制路径
                var polyline = new BMap.Polyline([
                    {path_js}
                ], {{
                    strokeColor: "#3388ff",
                    strokeWeight: 6,
                    strokeOpacity: 0.7
                }});
                map.addOverlay(polyline);

                // 添加标记
                {markers_js}

                // 自适应视野
                map.setViewport(polyline.getBounds());
            }}

            // 延迟加载防止API未就绪
            setTimeout(initialize, 500);
        </script>
    </body>
    </html>
    '''

def drag_sortable_list(items, key="sortable_list"):
    """生成可拖拽排序的列表组件（修复序号显示）"""
    if items is None or not isinstance(items, (list, tuple)):
        items = []

    items = list(items)

    session_key = f"sortable_{key}_value"

    component = html(
        f"""
        <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
        <div id="sortable-container" style="border: 1px solid #eee; padding: 10px; border-radius: 5px; margin: 10px 0;">
            <div id="sortable-list" style="list-style: none; padding: 0;">
                {"".join([
            f'<div style="cursor: move; padding: 8px; margin: 4px; background: #f8f9fa; border: 1px solid #ddd;" data-value="{item}">{item}</div>'
            for item in items
        ])}
            </div>
        </div>
        <script>
            const sortableList = document.getElementById('sortable-list');
            Sortable.create(sortableList, {{
                animation: 150,
                onUpdate: function(evt) {{
                    // 修复1：使用正确的作用域变量
                    Array.from(sortableList.children).forEach((item, currentIndex) => {{
                        item.textContent = (currentIndex + 1) + '. ' + item.dataset.value;
                    }});

                    // 修复2：简化数据提取逻辑
                    const newOrder = [];
                    sortableList.childNodes.forEach(node => {{
                        newOrder.push(node.dataset.value);
                    }});

                    // 更新session_state中的顺序
                    Streamlit.setComponentValue(newOrder);
                    setTimeout(() => Streamlit.setFrameHeight(), 100);
                }}
            }});
        </script>
        """,
        height=len(items) * 45 + 50,
    )

    if session_key in st.session_state:
        return st.session_state[session_key]
    # st.write("列表框中的顺序序",st.session_state.current_order)
    return items.copy()



def main():
    st.title("门店驾驶距离计算系统")
    # 获取当前文件所在目录的绝对路径
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DEFAULT_PATH = "门店详情.xlsx"

    # 初始化session_state配置
    if 'file_path' not in st.session_state:
        st.session_state.file_path = DEFAULT_PATH  # 设置默认路径

    # 使用缓存装饰器优化文件读取
    @st.cache_data
    def load_data(file_path):
        # 自动识别文件类型
        if file_path.endswith('.csv'):
            return pd.read_csv(file_path)
        else:
            return pd.read_excel(file_path, engine='openpyxl')

    # 主数据处理流程
    try:
        if 'df' not in st.session_state:
            # 首次加载时显示加载状态
            with st.spinner(f'正在加载数据文件：{st.session_state.file_path}'):
                df = load_data(st.session_state.file_path)

                # 数据验证
                required_cols = ['门店编码', '门店名称', 'latitude', 'longitude', '区域']
                missing_cols = [col for col in required_cols if col not in df.columns]
                if missing_cols:
                    st.error(f"缺少必要字段：{', '.join(missing_cols)}")
                    st.stop()

                # 数据清洗
                df = df.dropna(subset=['latitude', 'longitude'])  # 坐标不能为空
                df.fillna({'区域': '未知'}, inplace=True)

                st.session_state.df = df

        df = st.session_state.df

        # 显示数据摘要
        st.success(f"✅ 成功加载 {len(df)} 条门店数据")

    except FileNotFoundError:
        st.error(f"文件未找到：{st.session_state.file_path}，请检查："
                 f"\n1. 文件是否存在于项目根目录"
                 f"\n2. 文件名是否准确"
                 f"\n3. 文件扩展名是否正确")
    except PermissionError:
        st.error("文件访问被拒绝，请检查文件权限设置")
    except Exception as e:
        st.error(f"数据加载失败：{str(e)}")
        st.stop()

    # 选择业务类型
    business_type = st.selectbox("选择业务类型", options=["常温", "冷链"])
    def parse_store_batch(text: str):
        """
        把用户输入的字符串按照 空格 / 换行 / 逗号 进行切分，
        返回去重后的门店名列表（保持原顺序）
        """
        if not text:
            return []
        # 支持多种分隔符
        import re
        raw_parts = re.split(r"[ \n,，]+", text.strip())
        # 去掉空串并保持顺序去重
        seen, result = set(), []
        for p in raw_parts:
            if p and p not in seen:
                seen.add(p)
                result.append(p)
        return result

    if business_type == "常温":
        st.subheader("选择常温配送路线")
        if "pending_region_to_add" in st.session_state:
            # 把临时保存的区域同步到 multiselect
            new_region = st.session_state.pop("pending_region_to_add")
            cur = st.session_state.get("region_multiselect", [])
            if new_region not in cur:
                st.session_state["region_multiselect"] = cur + [new_region]
        # 获取所有区域
        valid_regions = df['区域'].unique().tolist()

        # 允许用户选择多个区域
        # ---------- 1. 选择区域（绑定 session_state） ----------
        selected_regions = st.multiselect(
            "选择区域",
            options=valid_regions,
            default=valid_regions[:1],  # 给个默认
            key="region_multiselect"  # ★ 用于后续动态修改
        )

        # 根据选择的区域筛选门店（未勾选高速时生效）
        stores_in_selected_regions = df[df['区域'].isin(selected_regions)]
        store_names = stores_in_selected_regions['门店名称'].unique().tolist()

        batch_text = st.text_input(
            "批量输入门店（空格/回车/逗号分隔，可直接粘贴）",
            placeholder="如：高升时代公寓_加盟 佳迎南食店 建芙蓉嘉苑_加盟",
            key = "batch_store_text"
        )

        # 解析批量输入
        batch_store_list = parse_store_batch(batch_text)

        # ---------- 3. 根据所选区域先算出可供选择的门店 ----------
        stores_in_selected_regions = df[df['区域'].isin(selected_regions)]
        store_names = stores_in_selected_regions['门店名称'].unique().tolist()
        if "仓库" not in store_names:
            store_names.append("仓库")

        # if not show_highway_only:  # 新增条件判断
        stores_in_selected_regions = df[df['区域'].isin(selected_regions)]
        store_names = stores_in_selected_regions['门店名称'].unique().tolist()
        if "仓库" not in store_names:
            store_names.append("仓库")
        # else:
        #     pass

            # ---------- 4. 把批量门店分三类 ----------
        valid_in_options = []  # 该门店已经在当前 option 里，可以直接 multiselect
        need_region_popup = []  # 该门店在数据库中有、但其区域未被选择
        not_found = []  # 数据里都不存在（可能是手输错误）

        for store in batch_store_list:
            row = df[df['门店名称'] == store]
            if not row.empty:
                region = row['区域'].iloc[0]
                if region in selected_regions:
                    valid_in_options.append(store)
                else:
                    need_region_popup.append((store, region))
            else:
                not_found.append(store)

        # ---------- 5. 组织 multiselect 的默认值 ----------
        default_selected = ['仓库'] + valid_in_options  # 始终包含仓库
        # 去重同时保证顺序
        default_selected = list(dict.fromkeys(default_selected))

        # ---------- 6. 真正的门店 multiselect（绝不会报错） ----------
        selected_stores = st.multiselect(
            '选择门店',
            options=["仓库"] + sorted([s for s in store_names if s != "仓库"]),
            default=default_selected,
            key="store_multiselect"
        )

        # ========== 7. 交互对话框部分 ==========
        if need_region_popup or not_found:
            with st.expander("⚠️ 批量输入校验结果 / 区域不匹配 👉 查看处理"):
                # 7.1 区域不匹配
                for store, region in need_region_popup:
                    st.warning(f"门店【{store}】属于区域【{region}】，但当前未选择该区域。")
                    cols = st.columns(1)
                    # --- 按钮 1：把区域加进 multiselect ---
                    if cols[0].button(f"✔ 添加 {region}", key=f"add_{store}"):
                        # 这里只写中转键，不直接改 multiselect
                        st.session_state["pending_region_to_add"] = region
                        st.rerun()

                # 7.2 根本查不到的门店
                if not_found:
                    st.error("数据库中未找到： " + "、".join(not_found))
                    if st.button("从批量输入中删除这些无效门店", key="delete_notfound"):
                        remain_store = [s for s in batch_store_list if s not in not_found]
                        st.session_state.batch_store_text = " ".join(remain_store)
                        st.rerun()
        missing_from_select = [
            s for s in batch_store_list
            if s not in selected_stores and s in store_names
        ]
        if missing_from_select:
            # 更新 multiselect 选项（会触发一次 rerun）
            st.session_state.store_multiselect = selected_stores + missing_from_select
            st.experimental_rerun()

        filtered_stores = stores_in_selected_regions[stores_in_selected_regions['门店名称'].isin(selected_stores)]

        # 如果“仓库”被选中但不在当前区域中，手动添加它
        if "仓库" in selected_stores and "仓库" not in filtered_stores['门店名称'].values:
            warehouse_row = df[df['门店名称'] == "仓库"].iloc[0]  # 假设“仓库”在数据中是唯一的
            filtered_stores = pd.concat([pd.DataFrame([warehouse_row]), filtered_stores], ignore_index=True)

        # 按用户选择顺序排序
        sorted_stores = filtered_stores.copy()
        sorted_stores['配送序号'] = sorted_stores['门店名称'].apply(lambda x: selected_stores.index(x))
        sorted_stores = sorted_stores.sort_values(by='配送序号')

    elif business_type == "冷链":
        st.subheader("选择冷链路线号")
        if '冷链路线' in df.columns:
            df['冷链路线'] = df['冷链路线'].fillna('')  # 将NaN替换为空字符串
            valid_routes = [route for route in df['冷链路线'].unique() if route not in ['', '未知']]  # 过滤掉空值和"未知"路线


            # 在冷链分支添加仓库时捕获异常
            try:
                warehouse_row = df[df['门店名称'] == "仓库"].iloc[0]
            except IndexError:
                st.error("数据中未找到仓库信息，请检查数据文件！")
                st.stop()

            # 添加选择框
            if len(valid_routes) > 0:
                cold_chain_route = st.selectbox(
                    "选择冷链路线号：",
                    options=valid_routes,  # 只显示有效路线
                    index=0  # 默认选中第一个有效选项
                )

                # 根据选择的冷链路线过滤门店
                stores_in_selected_route = df[df['冷链路线'] == cold_chain_route]
                store_names = stores_in_selected_route['门店名称'].unique().tolist()

                store_names = stores_in_selected_route['门店名称'].unique().tolist()
                if "仓库" not in store_names:
                    store_names.append("仓库")

                # 强制仓库在首位
                store_names = ["仓库"] + [name for name in store_names if name != "仓库"]
                default_selected = ["仓库"]

                selected_stores = st.multiselect(
                    "选择门店",
                    options=store_names,
                    default=default_selected
                )

                # # 过滤逻辑同步修改
                # if show_highway_only:
                #     filtered_stores = df[df['门店名称'].isin(selected_stores)]
                # else:
                filtered_stores = stores_in_selected_route[
                    stores_in_selected_route['门店名称'].isin(selected_stores)]
                # 如果“仓库”被选中但不在当前冷链路线中，手动添加它
                if "仓库" in selected_stores and "仓库" not in filtered_stores['门店名称'].values:
                    warehouse_row = df[df['门店名称'] == "仓库"].iloc[0]  # 假设“仓库”在数据中是唯一的
                    filtered_stores['冷链送货序号'] = pd.to_numeric(filtered_stores['冷链送货序号'],
                                                                    errors='coerce')
                    sorted_stores = filtered_stores.sort_values(by='冷链送货序号')
                # 排序处理（冷链按冷链送货序号排序）
                if '冷链送货序号' in filtered_stores.columns:
                    sorted_stores = filtered_stores.sort_values(by='冷链送货序号')
                else:
                    sorted_stores = filtered_stores
                    st.info("数据中缺少冷链送货序号字段，使用原始排序")

            else:
                st.warning("没有可用的冷链路线数据")
                filtered_stores = df  # 显示全部数据
        else:
            st.warning("当前数据中未包含冷链路线信息")
            filtered_stores = df  # 显示全部数据

        # 添加仓库到门店列表
        warehouse = df[df['门店名称'] == "仓库"].iloc[0]
        selected_stores_in_order = [warehouse_row] + [row for _, row in filtered_stores.iterrows() if
                                                      row['门店名称'] != "仓库"]
        sorted_stores = pd.DataFrame(selected_stores_in_order)

    if len(sorted_stores) > 1:

        # 计算路径和生成地图
        path_points, total_distance, total_duration = [], 0, 0
        sorted_coordinates = sorted_stores[['longitude', 'latitude']].values.tolist()

        if len(sorted_coordinates) >= 2:
            # 每次重新计算完整路径
            with st.spinner("正在重新计算路线..."):
                path_points.clear()
                for i in range(len(sorted_coordinates) - 1):
                    origin = sorted_coordinates[i]
                    dest = sorted_coordinates[i + 1]
                    route_data = get_driving_route(origin[0], origin[1], dest[0], dest[1])

                    if route_data:
                        path_points += route_data['processed_path']
                        total_distance += route_data['distance']
                        total_duration += route_data['duration']

        # 立即显示最新计算结果
        st.write(f"#### 总驾驶距离: {total_distance / 1000:.2f} km")
        st.write(f"#### 预计驾驶时间: {total_duration / 60:.2f} min")

        # 强制刷新地图
        if path_points:
            st.subheader("路线示意图")
            html(
                generate_baidu_map_html(
                    sorted_stores.to_dict(orient="records"),
                    path_points
                ),
                height=520,
                # key=f"map_{hash(tuple(st.session_state.current_order))}"  # 通过哈希值强制刷新组件
            )
        else:
            st.warning("未能获取有效路径，请检查坐标数据")


if __name__ == "__main__":
    main()