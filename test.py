import streamlit as st
import pandas as pd
import requests
from streamlit.components.v1 import html

# 百度地图配置
SERVER_AK = "j44ZAQiQcNRl4IfSAA2DqTeWyWCQkjKg"  # 服务端类型应用
BROWSER_AK = "F2h8URNdw483r3LQXY7xE1Q8hknD1dRy"  # 浏览器端类型应用
DIRECTION_API_URL = "https://api.map.baidu.com/direction/v2/driving"
st.write("所有 Secrets 键名:", list(st.secrets.keys()))
st.write("PASSWORD 的值是否存在:", "PASSWORD" in st.secrets)

if "PASSWORD" not in st.secrets:
    st.error("❌ Secrets 未正确配置，请检查云端设置！")
    st.stop()

password = st.text_input("请输入密码", type="password")
correct_password = st.secrets["PASSWORD"]

if password != correct_password:
    st.error("密码错误")
    st.stop()

st.success("✅ 密码正确！")
# 以下是应用的正式内容
st.write("欢迎访问受保护的应用！")
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


def main():
    st.title("门店驾驶距离计算系统")
    uploaded_file = st.file_uploader("上传门店数据文件（CSV/Excel）", type=["csv", "xlsx"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        required_cols = ['门店编码', '门店名称', 'latitude', 'longitude', '区域']
        if not all(col in df.columns for col in required_cols):
            st.error("文件缺少必要列")
            return
        df.fillna("未知", inplace=True)
        st.session_state.df = df
        st.success(f"成功加载 {len(df)} 家门店数据")

        # 选择业务类型
        business_type = st.selectbox("选择业务类型", options=["常温", "冷链"])

        # 根据业务类型选择不同的路线
        if business_type == "常温":
            st.subheader("选择常温配送路线")

            # 获取所有区域
            valid_regions = df['区域'].unique().tolist()

            # 允许用户选择多个区域
            selected_regions = st.multiselect("选择区域", options=valid_regions, default=valid_regions[0])

            # 根据选择的区域筛选门店
            stores_in_selected_regions = df[df['区域'].isin(selected_regions)]
            store_names = stores_in_selected_regions['门店名称'].unique().tolist()

            # 确保“仓库”始终在门店列表中，即使它不属于所选区域
            if "仓库" not in store_names:
                store_names.append("仓库")

            # 确保“仓库”始终在默认值中
            default_stores = ["仓库"]

            # 选择门店（默认包含仓库）
            selected_stores = st.multiselect("选择门店", store_names, default=default_stores)

            # 过滤选择的门店
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

                    # 确保“仓库”始终在门店列表中，即使它不属于所选冷链路线
                    if "仓库" not in store_names:
                        store_names.append("仓库")

                    # 默认选择“仓库”加该冷链路线下的所有门店
                    default_stores = ["仓库"] + store_names

                    # 选择门店（默认包含仓库）
                    selected_stores = st.multiselect("选择门店", store_names, default=default_stores)

                    # 过滤选择的门店
                    filtered_stores = stores_in_selected_route[stores_in_selected_route['门店名称'].isin(selected_stores)]

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
            sorted_stores = pd.concat([warehouse.to_frame().T, sorted_stores], ignore_index=True)

        # 显示门店列表
        st.subheader("门店列表")
        st.dataframe(sorted_stores[['门店名称', 'latitude', 'longitude']])

        # 计算路径
        if len(sorted_stores) > 1:
            path_points, total_distance, total_duration = [], 0, 0
            for i in range(len(sorted_stores) - 1):
                store1, store2 = sorted_stores.iloc[i], sorted_stores.iloc[i + 1]
                route_data = get_driving_route(
                    store1['longitude'], store1['latitude'],
                    store2['longitude'], store2['latitude']
                )
                if route_data:
                    path_points.extend(route_data['processed_path'])
                    total_distance += route_data['distance']
                    total_duration += route_data['duration']

            # 添加路径点总数检查
            if len(path_points) == 0:
                st.error("警告：未获取到任何路径点，请检查坐标数据")
            else:
                st.write(f"总路径点数量：{len(path_points)}")
            st.subheader("路线示意图")
            html(generate_baidu_map_html(sorted_stores.to_dict(orient="records"), path_points), height=520)
            st.write(f"### 总驾驶距离: {total_distance / 1000:.2f} km")
            st.write(f"### 预计驾驶时间: {total_duration / 60:.2f} min")



if __name__ == "__main__":
    main()
