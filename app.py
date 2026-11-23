if uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    required_cols = {"Category", "Budget", "Actual"}
    if not required_cols.issubset(df.columns):
        st.error(f"Kolom wajib harus ada: {', '.join(sorted(required_cols))}")
        st.stop()

    df["Budget"] = pd.to_numeric(df["Budget"], errors="coerce").fillna(0)
    df["Actual"] = pd.to_numeric(df["Actual"], errors="coerce").fillna(0)
    df["Variance"] = df["Actual"] - df["Budget"]
    df["Variance_Pct"] = df.apply(
        lambda r: ((r["Actual"] - r["Budget"]) / r["Budget"] * 100) if r["Budget"] != 0 else 0.0,
        axis=1,
    )
    df["Status"] = df["Variance"].apply(
        lambda v: "Over Budget" if v > 0 else ("Under Budget" if v < 0 else "On Budget")
    )

    total_budget = df["Budget"].sum()
    total_actual = df["Actual"].sum()
    total_variance = total_actual - total_budget
    total_var_pct = (total_variance / total_budget * 100) if total_budget != 0 else 0.0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Budget", f"{total_budget:,.2f}")
    c2.metric("Total Actual", f"{total_actual:,.2f}")
    c3.metric("Total Variance", f"{total_variance:+,.2f}", f"{total_var_pct:+.2f}%")

    st.subheader("Ringkasan Tabel Varians")
    st.dataframe(df, use_container_width=True)

    st.subheader("Perbandingan Budget vs. Actual")
    df_melted = df.melt(id_vars="Category", value_vars=["Budget", "Actual"], var_name="Type", value_name="Amount")
    fig = px.bar(df_melted, x="Category", y="Amount", color="Type", barmode="group")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Komentar & Insight AI (Groq)")
    if st.button("Generate AI Commentary"):
        client = Groq(api_key=GROQ_API_KEY)
        summary_text = df[["Category", "Budget", "Actual", "Variance", "Variance_Pct", "Status"]].to_string(index=False)
        prompt = (
            "Kamu adalah analis keuangan. Berikan ringkasan varians Budget vs. Actual secara singkat, "
            "jelas, dan actionable dalam bahasa Indonesia berdasarkan data berikut:\n\n"
            f"Total Budget: {total_budget:,.2f}, Total Actual: {total_actual:,.2f}, Total Variance: {total_variance:+,.2f} ({total_var_pct:+.2f}%)\n"
            f"{summary_text}"
        )
        with st.spinner("Menghasilkan analisis AI..."):
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
        st.markdown(completion.choices[0].message.content)